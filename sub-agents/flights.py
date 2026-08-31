"""
flights.py — Flight recommendation sub-agent (Google ADK)

Responsibilities (per architecture):
  - Given a trip's origin/destination airports and the first and last
    scheduled tournament events, search candidate outbound and return
    flights and rank them.
  - Enforce that the recommended outbound flight actually arrives with
    enough buffer before the first event — a cheap flight that lands
    too late to make check-in isn't a valid recommendation.
  - If nothing at the primary destination airport fits the required
    arrival window or budget (common on tournament weekends when demand
    spikes into one airport), widen the search to a nearby alternate
    airport rather than silently returning nothing.
  - Returns structured recommendations only. It does NOT purchase the
    ticket, charge a card, send confirmation emails, or touch the
    calendar — those are orchestrator responsibilities per the
    confirmation state-machine design.

This agent is meant to be mounted as a sub_agent of the orchestrator
agent (see orchestrator.py), which handles session state, the
"Type YES to confirm" flow, and side effects (email, calendar, Firestore
writes to `registrations` / `bookings`).

Data layer notes:
  - `get_trip_requirements`, `search_flights`, and
    `search_alternate_airports` are stubbed here. In production, wire
    them to Firestore (`trips`, `tournaments` collections per the
    schema discussed) and to a real flight search API (e.g. Amadeus,
    Duffel, Skyscanner) or a synced fare dataset.
  - `first_event_datetime` / `last_event_end_datetime` should come from
    the earliest and latest entries in tournament.schedule, not just
    the tournament's start_date/end_date, since practice or check-in
    events can fall outside that range.
  - Keep these as plain functions decorated as ADK tools — ADK reads
    the function signature + docstring to build the tool schema, so
    keep type hints and docstrings accurate.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

from google.adk.agents import Agent
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_store

MODEL = "gemini-3.6-flash"


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class FlightLeg(BaseModel):
    direction: Literal["outbound", "return"]
    flight_id: str
    airline: str
    price: float
    depart_time: str = Field(description="ISO datetime")
    arrive_time: str = Field(description="ISO datetime")
    layovers: int
    recommendation_note: str = Field(
        description="Why this flight fits, given timing, budget, and layovers"
    )


class FlightRecommendationResponse(BaseModel):
    search_scope: Literal["primary_airport", "alternate_airport"] = Field(
        description=(
            "'alternate_airport' if the primary destination airport had no "
            "options meeting the arrival window or budget, requiring a "
            "search near a secondary airport"
        )
    )
    within_budget_available: bool = Field(
        description="Whether at least one round-trip combination meets budget_max"
    )
    arrival_buffer_ok: bool = Field(
        description=(
            "Whether at least one outbound option arrives before "
            "first_event_datetime minus arrival_buffer_minutes"
        )
    )
    options: list[FlightLeg] = Field(
        description="Up to 3 outbound legs and up to 3 return legs, tagged by direction"
    )
    reasoning: str = Field(description="Plain-language summary for the athlete/parent")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_trip_requirements(trip_id: str) -> dict:
    """Fetch airports, event timing, and budget/flexibility preferences for a trip.

    Args:
        trip_id: Unique identifier for the trip (Firestore doc id under
            the `trips` collection).

    Returns:
        A dict with 'origin_airport', 'destination_airport',
        'first_event_datetime', 'last_event_end_datetime',
        'arrival_buffer_minutes', 'budget_max', and
        'departure_flexibility_hours'.
    """
    trip = data_store.get_trip(trip_id)
    if trip:
        return {
            "origin_airport": trip["origin_airport"],
            "destination_airport": trip["destination_airport"],
            "first_event_datetime": trip["first_event_datetime"],
            "last_event_end_datetime": trip["last_event_end_datetime"],
            "arrival_buffer_minutes": trip.get("arrival_buffer_minutes", 180),
            "budget_max": trip.get("budget_max", 450),
            "departure_flexibility_hours": trip.get("departure_flexibility_hours", 6),
        }
    # Fallback for a trip_id that isn't in the store (e.g. the __main__
    # smoke test below) — TODO: replace with a real Firestore read once
    # trips move off the local store, e.g.
    #   trip = db.collection("trips").document(trip_id).get().to_dict()
    return {
        "origin_airport": "SAN",
        "destination_airport": "LAX",
        "first_event_datetime": "2026-09-29T09:00:00",
        "last_event_end_datetime": "2026-09-30T18:00:00",
        "arrival_buffer_minutes": 180,
        "budget_max": 450,
        "departure_flexibility_hours": 6,
    }


def search_flights(
    origin_airport: str,
    destination_airport: str,
    earliest_datetime: str,
    latest_datetime: str,
    max_price: Optional[float] = None,
) -> list[dict]:
    """Search for one-way flights between two airports within a time window.

    Call this once per direction: origin -> destination for the outbound
    leg, and destination -> origin for the return leg, with each leg's
    own time window.

    Args:
        origin_airport: IATA code to depart from.
        destination_airport: IATA code to arrive at.
        earliest_datetime: ISO datetime; earliest acceptable time in
            this window (departure time for the search, interpreted by
            the caller relative to the direction being searched).
        latest_datetime: ISO datetime; latest acceptable time in this
            window.
        max_price: Optional price ceiling to filter results.

    Returns:
        A list of candidate flight dicts with id, airline, price,
        depart_time, arrive_time, and layovers.
    """
    # TODO: replace with a real query against a flight search API
    # (e.g. Amadeus, Duffel, Skyscanner) or a synced fare dataset.
    #
    # Candidate times are generated as offsets from earliest_datetime rather
    # than hardcoded absolute dates, so this mock stays coherent no matter
    # which trip it's asked about — a fixed date would silently mismatch
    # every event window except the one it was written for.
    try:
        base = datetime.fromisoformat(earliest_datetime)
    except (ValueError, TypeError):
        base = datetime.now()
    candidates = [
        ("aa-1423", "American Airlines", 214.0, 30, 85, 0),
        ("dl-889", "Delta", 268.0, -420, 87, 0),
        ("ua-4410", "United", 189.0, -120, 215, 1),
    ]
    results = []
    for flight_id, airline, price, offset_minutes, duration_minutes, layovers in candidates:
        depart = base + timedelta(minutes=offset_minutes)
        arrive = depart + timedelta(minutes=duration_minutes)
        results.append(
            {
                "flight_id": flight_id,
                "airline": airline,
                "price": price,
                "depart_time": depart.isoformat(),
                "arrive_time": arrive.isoformat(),
                "layovers": layovers,
            }
        )
    return results


def search_alternate_airports(
    origin_airport: str,
    destination_metro: str,
    earliest_datetime: str,
    latest_datetime: str,
) -> list[dict]:
    """Search flights using a secondary airport near the destination metro.

    Used when the primary destination airport has no options that fit
    the required arrival window or budget (common on major tournament
    weekends when demand spikes into one airport).

    Args:
        origin_airport: IATA code to depart from.
        destination_metro: City/region name to find an alternate airport
            near (e.g. 'Los Angeles, CA').
        earliest_datetime: ISO datetime lower bound.
        latest_datetime: ISO datetime upper bound.

    Returns:
        A list of candidate flight dicts, same shape as search_flights,
        plus an 'arrival_airport' field noting which alternate was used.
    """
    # TODO: wire to the same data source as search_flights, querying a
    # secondary airport code (e.g. BUR or LGB instead of LAX) near the
    # requested metro.
    try:
        base = datetime.fromisoformat(earliest_datetime)
    except (ValueError, TypeError):
        base = datetime.now()
    depart = base - timedelta(minutes=45)
    arrive = depart + timedelta(minutes=85)
    return [
        {
            "flight_id": "wn-2210",
            "airline": "Southwest",
            "price": 176.0,
            "depart_time": depart.isoformat(),
            "arrive_time": arrive.isoformat(),
            "layovers": 0,
            "arrival_airport": "BUR",
        },
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

flight_agent = Agent(
    name="flight_agent",
    model=MODEL,
    description=(
        "Recommends outbound and return flights for a trip, balancing "
        "budget, arrival timing ahead of the first scheduled event, and "
        "layovers."
    ),
    instruction="""
You are the flight recommendation agent for an athlete logistics
assistant. You are called by an orchestrator agent — you never talk to
the athlete directly and you never purchase, charge, or confirm a
flight.

Steps:
1. Call get_trip_requirements to load the origin/destination airports,
   first_event_datetime, last_event_end_datetime,
   arrival_buffer_minutes, budget_max, and departure_flexibility_hours
   for this trip.
2. Compute the outbound search window: flights must arrive no later
   than (first_event_datetime - arrival_buffer_minutes). Use
   departure_flexibility_hours to set how early the search window can
   start.
3. Compute the return search window: flights must depart no earlier
   than a reasonable buffer after last_event_end_datetime, again using
   departure_flexibility_hours for how late the window can extend.
4. Call search_flights twice: once for the outbound leg (origin ->
   destination, outbound window), once for the return leg (destination
   -> origin, return window).
5. Rank each leg's results primarily by whether they respect the
   required arrival/departure window, then by price, then by fewest
   layovers.
6. If no outbound option arrives within the required buffer before the
   first event, OR nothing at the primary airport pair is within
   budget_max, call search_alternate_airports and set search_scope to
   'alternate_airport'. Call out the added ground-transport tradeoff in
   recommendation_note when you do this.
7. Set arrival_buffer_ok to false if even the alternate-airport search
   cannot produce an outbound option respecting arrival_buffer_minutes —
   this tells the orchestrator to flag a real scheduling risk to the
   athlete rather than silently booking a flight that risks a missed
   check-in.
8. Return at most 3 ranked options per direction. Never invent flights,
   prices, airlines, or times that didn't come from a tool call.
""",
    tools=[get_trip_requirements, search_flights, search_alternate_airports],
    output_schema=FlightRecommendationResponse,
    output_key="flight_recommendation",
)


# Exposed for mounting under the orchestrator, e.g.:
#   from flights import flight_agent
#   orchestrator = Agent(name="orchestrator", sub_agents=[flight_agent, hotel_agent, tournament_agent, ...])
root_agent = flight_agent


if __name__ == "__main__":
    # Local smoke test via ADK's Runner + in-memory session service.
    import asyncio

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def main() -> None:
        runner = InMemoryRunner(agent=flight_agent, app_name="flights_dev")
        session = await runner.session_service.create_session(
            app_name="flights_dev", user_id="demo_player"
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Find me flights for trip_id demo-trip-001.")],
        )
        async for event in runner.run_async(
            user_id="demo_player", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)

    asyncio.run(main())