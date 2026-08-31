"""
data_store.py — Local JSON-backed persistence for the dashboard API.

Stands in for the Firestore collections the ADK agents already
reference (`tournaments`, `registrations`, `search_history`) and the
journal entries the dashboard needs, so the app runs end-to-end without
GCP credentials configured. Swap a function's body for a real
`firestore.Client()` read/write once credentials are available — the
shapes returned here already match the collection schemas described in
orchestrator.py's module docstring.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from pathlib import Path
from typing import Callable

_PATH = Path(__file__).parent / "data" / "local_store.json"
_LOCK = threading.Lock()

_DEFAULT = {
    "players": [],
    "tournaments": [],
    "flights": [],
    "hotels": [],
    "journal": [],
    "bookings": [],
    "search_history": [],
    "trips": [],
}

# Returned by get_player() for an id that isn't in the store yet (e.g. the
# demo player, or an ADK smoke test). Mirrors the get_trip() fallbacks the
# flight/hotel agents use so the full recommendation flow still exercises
# without a provisioned `players` collection.
_DEMO_PLAYER = {
    "player_id": "demo-player",
    "ranking": 842,
    "recent_matches": [
        {"date": "2026-08-10", "result": "L", "round": "R1", "opponent_level": "Challenger"},
        {"date": "2026-07-28", "result": "L", "round": "R1", "opponent_level": "Challenger"},
        {"date": "2026-07-12", "result": "W", "round": "QF", "opponent_level": "Futures"},
    ],
    "location_pref": "San Diego, CA",
}


def _load() -> dict:
    if not _PATH.exists():
        return {k: list(v) for k, v in _DEFAULT.items()}
    with _PATH.open() as f:
        data = json.load(f)
    for k, v in _DEFAULT.items():
        data.setdefault(k, list(v))
    return data


def _save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with _PATH.open("w") as f:
        json.dump(data, f, indent=2)


def _mutate(fn: Callable[[dict], None]) -> None:
    with _LOCK:
        data = _load()
        fn(data)
        _save(data)


def list_tournaments() -> list[dict]:
    return _load()["tournaments"]


def clear_tournaments() -> None:
    """Wipe stored tournaments. Called on server startup so stale search
    results from a previous run don't linger — tournament data is a search
    cache, re-populated on demand, unlike journal entries/bookings."""

    def op(data: dict) -> None:
        data["tournaments"] = []

    _mutate(op)


def _upsert(collection: str, items: list[dict], key: str = "id") -> None:
    """Upsert by `key` so re-running a search/write doesn't duplicate rows."""

    def op(data: dict) -> None:
        rows = data[collection]
        by_id = {r.get(key): i for i, r in enumerate(rows)}
        for item in items:
            iid = item.get(key)
            if iid in by_id:
                rows[by_id[iid]] = item
            else:
                rows.append(item)
                by_id[iid] = len(rows) - 1

    _mutate(op)


# ---------------------------------------------------------------------------
# players — stands in for the Firestore `players` collection the tournament
# agent reads (ranking + recent match history to reason about form).
# ---------------------------------------------------------------------------

def list_players() -> list[dict]:
    return _load()["players"]


def get_player(player_id: str) -> dict | None:
    """Look a player up by id, falling back to the demo profile for the
    demo/unset id so the tournament agent always has something to reason
    about. Returns None for a genuinely unknown, non-demo id."""
    player = next(
        (p for p in _load()["players"] if p.get("player_id") == player_id),
        None,
    )
    if player:
        return player
    if player_id in (None, "", "demo-player", "demo_player", "demo_player_id"):
        return dict(_DEMO_PLAYER)
    return None


def save_player(fields: dict) -> dict:
    player = dict(fields)
    player.setdefault("player_id", uuid.uuid4().hex)
    _upsert("players", [player], key="player_id")
    return player


def add_tournaments(new_tournaments: list[dict]) -> None:
    _upsert("tournaments", new_tournaments)


def list_flights() -> list[dict]:
    return _load()["flights"]


def add_flights(new_flights: list[dict]) -> None:
    _upsert("flights", new_flights)


def list_hotels() -> list[dict]:
    return _load()["hotels"]


def add_hotels(new_hotels: list[dict]) -> None:
    _upsert("hotels", new_hotels)


def get_trip(trip_id: str) -> dict | None:
    return next((t for t in _load()["trips"] if t.get("trip_id") == trip_id), None)


def save_trip(fields: dict) -> dict:
    """Store a trip built from a chosen tournament — flights.py/hotels.py's
    get_trip_requirements()/get_trip_lodging_requirements() read it back by
    trip_id to derive dates, destination, and budget for their agents."""
    trip = dict(fields)
    trip.setdefault("trip_id", uuid.uuid4().hex)
    _mutate(lambda data: data["trips"].append(trip))
    return trip


def list_journal(user_id: str) -> list[dict]:
    entries = [e for e in _load()["journal"] if e.get("user_id") == user_id]
    return sorted(entries, key=lambda e: e.get("date", ""), reverse=True)


def add_journal_entry(fields: dict) -> dict:
    entry = dict(fields)
    entry.setdefault("id", uuid.uuid4().hex)
    entry.setdefault("date", dt.date.today().isoformat())
    _mutate(lambda data: data["journal"].append(entry))
    return entry


def list_bookings(user_id: str | None = None) -> list[dict]:
    bookings = _load()["bookings"]
    if user_id:
        return [b for b in bookings if b.get("user_id") == user_id]
    return bookings


def add_booking(fields: dict) -> dict:
    booking = dict(fields)
    booking.setdefault("id", uuid.uuid4().hex)
    booking.setdefault("reminder_sent", False)
    _mutate(lambda data: data["bookings"].append(booking))
    return booking


def mark_reminder_sent(booking_id: str) -> None:
    """Flip reminder_sent=True on one booking. Used by orchestrator's
    reminder_job so a re-run the same day doesn't double-send."""

    def op(data: dict) -> None:
        for b in data["bookings"]:
            if b.get("id") == booking_id:
                b["reminder_sent"] = True

    _mutate(op)


def add_search_history(entry: dict) -> None:
    _mutate(lambda data: data["search_history"].append(entry))
