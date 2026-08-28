"""
hotels.py — Hotel recommendation sub-agent (Google ADK)

Responsibilities (per architecture):
  - Given a trip's venue location and first/last scheduled tournament
    events, search candidate hotels near the venue and rank them.
  - Derive check-in/check-out from the same event timing flights.py
    uses (arrive the night before the first event, leave the morning
    after the last event ends) rather than asking the orchestrator to
    compute dates separately.
  - If nothing near the venue fits budget (common on tournament
    weekends when local hotels sell out or surge in price), widen the
    search radius rather than silently returning nothing.
  - Returns structured recommendations only. It does NOT book the
    room, charge a card, send confirmation emails, or touch the
    calendar — those are orchestrator responsibilities per the
    confirmation state-machine design.

This agent is meant to be mounted as a sub_agent of the orchestrator
agent (see orchestrator.py), which handles session state, the
"Type YES to confirm" flow, and side effects (email, calendar, Firestore
writes to `registrations` / `bookings`).

Data layer notes:
  - `get_trip_lodging_requirements`, `search_hotels`, and
    `search_wider_radius` are stubbed here. In production, wire them to
    Firestore (the same `trips` collection flights.py reads from) and
    to a real hotel search API (e.g. Booking.com affiliate API,
    Amadeus Hotel Search) or a synced inventory dataset.
  - This reads from the same `trips` collection as flights.py — no
    separate `hotel_trips` table. A trip has one venue location and one
    event window; both sub-agents derive their own dates/legs from it.
  - Keep these as plain functions decorated as ADK tools — ADK reads
    the function signature + docstring to build the tool schema, so
    keep type hints and docstrings accurate.
"""

from __future__ import annotations

from typing import Literal

from google.adk.agents import Agent
from pydantic import BaseModel, Field

MODEL = "gemini-3.5-flash"


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class HotelOption(BaseModel):
    hotel_id: str
    name: str
    address: str
    price_per_night: float
    total_price: float
    distance_note: str = Field(description="e.g. '0.8 mi from venue'")
    recommendation_note: str = Field(
        description="Why this hotel fits, given distance, price, and dates"
    )


class HotelRecommendationResponse(BaseModel):
    search_scope: Literal["near_venue", "wider_radius"] = Field(
        description=(
            "'wider_radius' if nothing near the venue fit budget, requiring "
            "a search further from the venue"
        )
    )
    within_budget_available: bool = Field(
        description="Whether at least one option meets budget_per_night"
    )
    options: list[HotelOption] = Field(description="Up to 3 ranked options")
    reasoning: str = Field(description="Plain-language summary for the athlete/parent")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_trip_lodging_requirements(trip_id: str) -> dict:
    """Fetch venue location, event timing, and lodging budget for a trip.

    Args:
        trip_id: Unique identifier for the trip (Firestore doc id under
            the `trips` collection — the same collection flights.py
            reads from).

    Returns:
        A dict with 'venue_location', 'first_event_datetime',
        'last_event_end_datetime', 'budget_per_night', and
        'prefers_near_venue'.
    """
    # TODO: replace with a real Firestore read, e.g.
    #   trip = db.collection("trips").document(trip_id).get().to_dict()
    return {
        "venue_location": "Barnes Tennis Center, San Diego, CA",
        "first_event_datetime": "2026-09-29T09:00:00",
        "last_event_end_datetime": "2026-09-30T18:00:00",
        "budget_per_night": 150,
        "prefers_near_venue": True,
    }


def search_hotels(
    location: str, check_in: str, check_out: str, budget_per_night: float
) -> list[dict]:
    """Search for hotels near a location for a given date range and budget.

    Args:
        location: Venue or city to search near.
        check_in: ISO date, e.g. 2026-09-28 — should be the night
            before first_event_datetime so the athlete isn't traveling
            the morning of.
        check_out: ISO date, e.g. 2026-09-30 — should be the morning
            after last_event_end_datetime.
        budget_per_night: Max price per night in USD.

    Returns:
        A list of candidate hotel dicts with id, name, address,
        price_per_night, total_price, and distance_note.
    """
    # TODO: replace with a real call to a hotel search API (e.g.
    # Booking.com affiliate API, Amadeus Hotel Search).
    nights = 2
    return [
        {
            "hotel_id": "hi-express-sd-1",
            "name": "Holiday Inn Express San Diego Airport",
            "address": "1600 Pacific Hwy, San Diego, CA",
            "price_per_night": 139.0,
            "total_price": 139.0 * nights,
            "distance_note": "1.2 mi from Barnes Tennis Center",
        },
        {
            "hotel_id": "la-quinta-sd-1",
            "name": "La Quinta Inn San Diego Airport",
            "address": "1010 Rosecrans St, San Diego, CA",
            "price_per_night": 119.0,
            "total_price": 119.0 * nights,
            "distance_note": "1.6 mi from Barnes Tennis Center",
        },
    ]


def search_wider_radius(
    location: str, check_in: str, check_out: str, budget_per_night: float, radius_miles: int = 15
) -> list[dict]:
    """Search for hotels in a wider radius when nothing near the venue fits budget.

    Used when search_hotels returns nothing within budget_per_night
    near the venue (common on tournament weekends when local hotels
    sell out or surge in price).

    Args:
        location: Venue or city to search around.
        check_in: ISO date for check-in.
        check_out: ISO date for check-out.
        budget_per_night: Max price per night in USD.
        radius_miles: How far out to widen the search.

    Returns:
        A list of candidate hotel dicts, same shape as search_hotels,
        with distance_note reflecting the greater distance from venue.
    """
    # TODO: wire to the same data source as search_hotels, with a
    # larger radius parameter passed to the underlying API.
    nights = 2
    return [
        {
            "hotel_id": "motel6-sd-1",
            "name": "Motel 6 San Diego - Mission Valley",
            "address": "2201 Hotel Cir S, San Diego, CA",
            "price_per_night": 89.0,
            "total_price": 89.0 * nights,
            "distance_note": "6.4 mi from Barnes Tennis Center",
        },
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

hotel_agent = Agent(
    name="hotel_agent",
    model=MODEL,
    description=(
        "Recommends hotels near a tournament venue, balancing distance, "
        "price, and the trip's event dates."
    ),
    instruction="""
You are the hotel recommendation agent for an athlete logistics
assistant. You are called by an orchestrator agent — you never talk to
the athlete directly and you never book, charge, or confirm a room.

Steps:
1. Call get_trip_lodging_requirements to load venue_location,
   first_event_datetime, last_event_end_datetime, budget_per_night,
   and prefers_near_venue for this trip.
2. Derive check_in as the calendar date before first_event_datetime
   (so the athlete isn't traveling the morning of competition) and
   check_out as the calendar date after last_event_end_datetime.
3. Call search_hotels with venue_location, the derived check_in/
   check_out, and budget_per_night.
4. Rank results primarily by whether they fit budget_per_night, then
   by distance to the venue, then by price.
5. If nothing near the venue fits budget_per_night, call
   search_wider_radius and set search_scope to 'wider_radius'. Call
   out the added commute tradeoff in recommendation_note when you do
   this.
6. Return at most 3 ranked options. Never invent hotels, prices, or
   addresses that didn't come from a tool call.
""",
    tools=[get_trip_lodging_requirements, search_hotels, search_wider_radius],
    output_schema=HotelRecommendationResponse,
    output_key="hotel_recommendation",
)

root_agent = hotel_agent


if __name__ == "__main__":
    import asyncio

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def main() -> None:
        runner = InMemoryRunner(agent=hotel_agent, app_name="hotels_dev")
        session = await runner.session_service.create_session(
            app_name="hotels_dev", user_id="demo_player"
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Find me a hotel for trip_id demo-trip-001.")],
        )
        async for event in runner.run_async(
            user_id="demo_player", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)

    asyncio.run(main())