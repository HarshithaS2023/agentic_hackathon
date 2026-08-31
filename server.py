"""
server.py — Flask API for the ORCA dashboard frontend.

Bridges frontend/src/api.js's /api/dashboard/* calls to:
  - the ADK orchestrator agent, for chat (/message) and its confirmation
    state machine (see orchestrator.py's module docstring)
  - the ADK tournament_search_agent, for the dashboard's human-triggered
    Google Search grounding pipeline (/search-tournaments)
  - data_store.py's local JSON persistence, for everything else
    (tournaments/flights/hotels lists, journal, bookings) — a stand-in
    for the Firestore collections those agents already reference.

Run with:  python3 server.py
frontend/vite.config.js proxies /api -> http://localhost:8080 in dev,
which is why this listens on port 8080 by default.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "sub-agents"))

from flask import Flask, jsonify, request
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types

import data_store
from orchestrator import orchestrator

app = Flask(__name__)

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

CHAT_APP_NAME = "orca_chat"
_chat_runner = InMemoryRunner(agent=orchestrator, app_name=CHAT_APP_NAME)
_chat_sessions: dict[str, str] = {}  # user_id -> session_id


def _chat_session_id(user_id: str) -> str:
    if user_id not in _chat_sessions:
        session = _loop.run_until_complete(
            _chat_runner.session_service.create_session(app_name=CHAT_APP_NAME, user_id=user_id)
        )
        _chat_sessions[user_id] = session.id
    return _chat_sessions[user_id]


def _run_chat(user_id: str, message: str) -> str:
    session_id = _chat_session_id(user_id)
    content = genai_types.Content(role="user", parts=[genai_types.Part(text=message)])

    async def _run() -> str:
        reply_parts = []
        async for event in _chat_runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        reply_parts.append(part.text)
        return "".join(reply_parts)

    return _loop.run_until_complete(_run())


def _run_tournament_search(user_id: str, sport: str, location: str, level: str) -> dict:
    from search import tournament_search_agent  # sub-agents/search.py

    search_app_name = "orca_tournament_search"
    runner = InMemoryRunner(agent=tournament_search_agent, app_name=search_app_name)

    # sport defaults to tennis — the rest of the app (player profiles, hotel/
    # flight stubs, USTA references) assumes tennis unless told otherwise.
    descriptor = " ".join(part for part in [level, sport or "tennis"] if part)
    query = f"Find upcoming {descriptor} tournaments"
    if location:
        query += f" near {location}"
    query += "."
    content = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])

    async def _run() -> dict:
        session = await runner.session_service.create_session(app_name=search_app_name, user_id=user_id)
        async for _event in runner.run_async(
            user_id=user_id, session_id=session.id, new_message=content
        ):
            pass
        final = await runner.session_service.get_session(
            app_name=search_app_name, user_id=user_id, session_id=session.id
        )
        return final.state.get("grounded_search_results") or {}

    return _loop.run_until_complete(_run())


def _find_tournament(name: str) -> dict | None:
    name_lower = name.strip().lower()
    for t in data_store.list_tournaments():
        if name_lower in t.get("name", "").lower():
            return t
    return None


# Tournament dates from grounded search are often messy free text (e.g.
# "June 29 – July 5, 2026" or "September 12–13, 2026"), not guaranteed ISO —
# see GroundedTournamentResult.date in search.py. Best-effort extraction,
# falling back to 30 days out, since the flight/hotel agents still need
# *some* concrete window to reason about.
_DATE_RANGE_RE = re.compile(r"([A-Z][a-z]+)\s+(\d{1,2})\s*[-–]\s*\d{1,2},?\s*(\d{4})")
_DATE_SINGLE_RE = re.compile(r"([A-Z][a-z]+)\s+(\d{1,2}),?\s*(\d{4})")


def _extract_event_window(raw_date: str) -> tuple[str, str]:
    match = _DATE_RANGE_RE.search(raw_date or "") or _DATE_SINGLE_RE.search(raw_date or "")
    first = None
    if match:
        month, day, year = match.groups()
        try:
            first = dt.datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
        except ValueError:
            first = None
    if first is None:
        first = dt.datetime.combine(dt.date.today() + dt.timedelta(days=30), dt.time())
    first = first.replace(hour=9, minute=0)
    last = first + dt.timedelta(days=1, hours=9)
    return first.isoformat(), last.isoformat()


def _run_flight_search(user_id: str, tournament: dict, origin: str) -> tuple[list[dict], str]:
    from flights import flight_agent  # sub-agents/flights.py

    first_iso, last_iso = _extract_event_window(tournament.get("date", ""))
    trip = data_store.save_trip(
        {
            "origin_airport": origin or "your home airport",
            "destination_airport": tournament.get("location", "the venue"),
            "first_event_datetime": first_iso,
            "last_event_end_datetime": last_iso,
            "arrival_buffer_minutes": 180,
            "budget_max": 500,
            "departure_flexibility_hours": 6,
        }
    )

    app_name = "orca_flight_search"
    runner = InMemoryRunner(agent=flight_agent, app_name=app_name)
    query = f"Find flights for trip_id {trip['trip_id']}."
    content = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])

    async def _run() -> dict:
        session = await runner.session_service.create_session(app_name=app_name, user_id=user_id)
        async for _event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
            pass
        final = await runner.session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session.id
        )
        return final.state.get("flight_recommendation") or {}

    output = _loop.run_until_complete(_run())

    rows = []
    for leg in output.get("options", []):
        rows.append(
            {
                # outbound/return legs can share a flight_id in the mock data —
                # suffix by direction so they don't clobber each other on upsert
                "id": f"{leg['flight_id']}-{leg['direction']}",
                "date": leg["depart_time"],
                "depart_time": leg["depart_time"],
                "arrive_time": leg["arrive_time"],
                "origin": trip["origin_airport"],
                "destination": trip["destination_airport"],
                "airline": leg["airline"],
                "price": leg["price"],
                "layovers": leg["layovers"],
                "direction": leg["direction"],
                # generic aliases the ORCA Search result-row renderer reads
                "name": f"{leg['airline']} ({leg['direction']})",
                "level": "Nonstop" if leg["layovers"] == 0 else f"{leg['layovers']} layover(s)",
                "location": f"{trip['origin_airport']} → {trip['destination_airport']}",
            }
        )
    return rows, output.get("reasoning", "")


def _run_hotel_search(user_id: str, tournament: dict) -> tuple[list[dict], str]:
    from hotels import hotel_agent  # sub-agents/hotels.py

    first_iso, last_iso = _extract_event_window(tournament.get("date", ""))
    first_dt, last_dt = dt.datetime.fromisoformat(first_iso), dt.datetime.fromisoformat(last_iso)
    check_in = (first_dt.date() - dt.timedelta(days=1)).isoformat()
    check_out = (last_dt.date() + dt.timedelta(days=1)).isoformat()
    nights = (dt.date.fromisoformat(check_out) - dt.date.fromisoformat(check_in)).days

    trip = data_store.save_trip(
        {
            "venue_location": tournament.get("location", ""),
            "first_event_datetime": first_iso,
            "last_event_end_datetime": last_iso,
            "budget_per_night": 150,
            "prefers_near_venue": True,
        }
    )

    app_name = "orca_hotel_search"
    runner = InMemoryRunner(agent=hotel_agent, app_name=app_name)
    query = f"Find a hotel for trip_id {trip['trip_id']}."
    content = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])

    async def _run() -> dict:
        session = await runner.session_service.create_session(app_name=app_name, user_id=user_id)
        async for _event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
            pass
        final = await runner.session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session.id
        )
        return final.state.get("hotel_recommendation") or {}

    output = _loop.run_until_complete(_run())

    rows = []
    for opt in output.get("options", []):
        rows.append(
            {
                "id": opt["hotel_id"],
                "name": opt["name"],
                "location": opt["address"],
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "price": opt["price_per_night"],
                "total_price": opt["total_price"],
                "distance_note": opt["distance_note"],
                # generic aliases the ORCA Search result-row renderer reads
                "date": check_in,
                "level": opt["distance_note"],
            }
        )
    return rows, output.get("reasoning", "")


@app.get("/api/dashboard/tournaments")
def get_tournaments():
    return jsonify({"tournaments": data_store.list_tournaments()})


@app.get("/api/dashboard/flights")
def get_flights():
    return jsonify({"flights": data_store.list_flights()})


@app.get("/api/dashboard/hotels")
def get_hotels():
    return jsonify({"hotels": data_store.list_hotels()})


@app.post("/api/dashboard/search-tournaments")
def search_tournaments_route():
    body = request.get_json(force=True) or {}
    kind = body.get("kind", "tournaments")
    user_id = body.get("user_id", "demo-player")

    if kind == "tournaments":
        sport = (body.get("sport") or "").strip()
        location = (body.get("location") or "").strip()
        level = (body.get("level") or "").strip()
        try:
            output = _run_tournament_search(user_id, sport, location, level)
        except Exception as exc:  # noqa: BLE001 — surface as a search failure, not a 500
            return jsonify({"results": [], "summary": f"Search failed: {exc}", "search_queries_used": []})
        return jsonify(
            {
                "results": output.get("results", []),
                "summary": output.get("summary", ""),
                "search_queries_used": output.get("search_queries_used", []),
            }
        )

    # Flights and hotels are both derived from a tournament you've already
    # found — no separate destination field, per the dashboard's design.
    tournament_name = (body.get("tournament") or "").strip()
    if not tournament_name:
        return jsonify(
            {
                "results": [],
                "summary": "Name a tournament first — find it in ORCA Search's Tournaments tab.",
                "search_queries_used": [],
            }
        )
    tournament = _find_tournament(tournament_name)
    if not tournament:
        return jsonify(
            {
                "results": [],
                "summary": f"Couldn't find a saved tournament matching '{tournament_name}'. Search for it first.",
                "search_queries_used": [],
            }
        )

    try:
        if kind == "flights":
            origin = (body.get("origin") or "").strip()
            rows, summary = _run_flight_search(user_id, tournament, origin)
            if rows:
                data_store.add_flights(rows)
        elif kind == "hotels":
            rows, summary = _run_hotel_search(user_id, tournament)
            if rows:
                data_store.add_hotels(rows)
        else:
            return jsonify({"results": [], "summary": f"Unknown search kind '{kind}'.", "search_queries_used": []})
    except Exception as exc:  # noqa: BLE001 — surface as a search failure, not a 500
        return jsonify({"results": [], "summary": f"Search failed: {exc}", "search_queries_used": []})

    return jsonify({"results": rows, "summary": summary, "search_queries_used": []})


@app.get("/api/dashboard/journal")
def get_journal():
    user_id = request.args.get("user_id", "demo-player")
    return jsonify({"entries": data_store.list_journal(user_id)})


@app.post("/api/dashboard/journal")
def create_journal_entry():
    body = request.get_json(force=True) or {}
    entry = data_store.add_journal_entry(
        {
            "user_id": body.get("user_id", "demo-player"),
            "log_type": body.get("log_type", "daily"),
            "log_title": body.get("log_title"),
            "energy_level": body.get("energy_level"),
            "hydration_status": body.get("hydration_status"),
            "soreness": {
                "present": bool(body.get("soreness_present")),
                "location": body.get("soreness_location"),
                "severity": body.get("soreness_severity"),
            },
            "performance_note": body.get("performance_note", ""),
        }
    )
    return jsonify(entry)


@app.post("/api/dashboard/message")
def send_message():
    body = request.get_json(force=True) or {}
    user_id = body.get("user_id", "demo-player")
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "Say something and I'll take a look."})

    try:
        reply = _run_chat(user_id, message)
    except Exception as exc:  # noqa: BLE001 — surface as a chat reply, not a 500
        return jsonify({"reply": f"Something went wrong reaching ORCA: {exc}"})

    return jsonify({"reply": reply or "I didn't catch that — try rephrasing."})


@app.get("/api/dashboard/bookings")
def get_bookings():
    user_id = request.args.get("user_id", "demo-player")
    return jsonify({"bookings": data_store.list_bookings(user_id)})


if __name__ == "__main__":
    import os

    data_store.clear_tournaments()

    port = int(os.environ.get("FLASK_PORT", 8080))
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_ENV") == "development")
