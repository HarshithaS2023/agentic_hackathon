"""
hotels.py — Hotel recommendation sub-agent (Google ADK)

Responsibilities (per architecture):
  - Given a trip's venue location, stay dates, and budget/quality
    preferences, find candidate hotels near the venue and rank them.
  - If nothing suitable is found near the venue (e.g. sold out on a
    tournament weekend), widen the search radius rather than silently
    returning nothing or returning venues far from the action without
    flagging it.
  - Returns structured recommendations only. It does NOT book the room,
    charge a card, send confirmation emails, or touch the calendar —
    those are orchestrator responsibilities per the confirmation
    state-machine design.

This agent is meant to be mounted as a sub_agent of the orchestrator
agent (see orchestrator.py), which handles session state, the
"Type YES to confirm" flow, and side effects (email, calendar, Firestore
writes to `registrations` / `bookings`).

Data layer notes:
  - `get_trip_requirements` and `search_hotels` are stubbed here.
    In production, wire them to Firestore (`trips`, `tournaments`
    collections per the schema discussed) and to whatever hotel data
    source you're using (a synced dataset or a live search API such as
    Google Places or Amadeus Hotel Search).
  - `get_trip_requirements` should prefer the athlete's already-booked
    flight dates (trip.booking.flight) for check-in/check-out when
    available, falling back to the tournament's start/end dates plus
    arrival_buffer_minutes otherwise.
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
    price_per_night: float
    distance_to_venue_miles: float
    rating: float = Field(description="Star rating, e.g. 3.5")
    recommendation_note: str = Field(
        description="Why this hotel fits, given budget, distance, and dates"
    )


class HotelRecommendationResponse(BaseModel):
    search_scope: Literal["near_venue", "expanded_radius"] = Field(
        description=(
            "'expanded_radius' if no suitable hotels were found within the "
            "normal radius of the venue and the search had to widen"
        )
    )
    checkin_date: str
    checkout_date: str
    within_budget_available: bool = Field(
        description="Whether at least one returned option meets budget_max"
    )
    options: list[HotelOption]
    reasoning: str = Field(description="Plain-language summary for the athlete/parent")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_trip_requirements(trip_id: str) -> dict:
    """Fetch venue location, stay dates, and lodging preferences for a trip.

    Args:
        trip_id: Unique identifier for the trip (Firestore doc id under
            the `trips` collection).

    Returns:
        A dict with 'venue_address', 'venue_coords', 'checkin_date',
        'checkout_date', 'budget_max', and 'hotel_min_stars'.
    """
    # TODO: replace with a real Firestore read, e.g.
    #   trip = db.collection("trips").document(trip_id).get().to_dict()
    # Prefer trip["booking"]["flight"] arrival/departure times for the
    # check-in/check-out dates when a flight has already been booked.
    return {
        "venue_address": "Barnes Tennis Center, San Diego, CA",
        "venue_coords": {"lat": 32.7757, "lng": -117.2264},
        "checkin_date": "2026-09-28",
        "checkout_date": "2026-09-30",
        "budget_max": 180,
        "hotel_min_stars": 3,
    }


def search_hotels(
    location: str, checkin_date: str, checkout_date: str, min_rating: float = 0.0
) -> list[dict]:
    """Search for hotels near a location for a given date range.

    Args:
        location: Address or place name to search near (typically the
            tournament venue).
        checkin_date: ISO date, e.g. '2026-09-28'.
        checkout_date: ISO date, e.g. '2026-09-30'.
        min_rating: Minimum star rating to include in results.

    Returns:
        A list of candidate hotel dicts with id, name, price_per_night,
        distance_to_venue_miles, and rating.
    """
    # TODO: replace with a real query — either a synced hotel dataset or
    # a live search API (e.g. Google Places, Amadeus Hotel Search).
    return [
        {
            "hotel_id": "sd-bayfront-inn",
            "name": "Bayfront Inn San Diego",
            "price_per_night": 149.0,
            "distance_to_venue_miles": 2.1,
            "rating": 3.5,
        },
        {
            "hotel_id": "sd-courtyard-airport",
            "name": "Courtyard San Diego Airport/Liberty Station",
            "price_per_night": 172.0,
            "distance_to_venue_miles": 3.4,
            "rating": 4.0,
        },
        {
            "hotel_id": "sd-luxe-harbor",
            "name": "Harbor View Suites",
            "price_per_night": 235.0,
            "distance_to_venue_miles": 1.2,
            "rating": 4.5,
        },
    ]


def search_hotels_expanded_radius(
    location: str, checkin_date: str, checkout_date: str, radius_miles: int = 20
) -> list[dict]:
    """Search a wider radius when nothing suitable is found near the venue.

    Used when the venue's immediate area is sold out (common on
    tournament weekends) or has no options meeting minimum quality bars.

    Args:
        location: Address or place name to search near (typically the
            tournament venue).
        checkin_date: ISO date, e.g. '2026-09-28'.
        checkout_date: ISO date, e.g. '2026-09-30'.
        radius_miles: How far out to widen the search.

    Returns:
        A list of candidate hotel dicts, same shape as search_hotels.
    """
    # TODO: wire to the same data source as search_hotels with a wider
    # geo radius parameter.
    return [
        {
            "hotel_id": "chula-vista-value-inn",
            "name": "Chula Vista Value Inn",
            "price_per_night": 118.0,
            "distance_to_venue_miles": 14.7,
            "rating": 3.0,
        },
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

hotel_agent = Agent(
    name="hotel_agent",
    model=MODEL,
    description=(
        "Recommends hotels near a tournament venue for a given trip, "
        "balancing budget, distance to venue, and minimum quality preferences."
    ),
    instruction="""
You are the hotel recommendation agent for an athlete logistics
assistant. You are called by an orchestrator agent — you never talk to
the athlete directly and you never book, charge, or confirm a hotel
reservation.

Steps:
1. Call get_trip_requirements to load the venue location, check-in/
   check-out dates, budget_max, and hotel_min_stars for this trip.
2. Call search_hotels using the venue location and the check-in/
   check-out dates.
3. Filter and rank the results:
   - Discard anything below hotel_min_stars unless it is the only
     option available.
   - Prefer hotels closer to the venue, especially when the trip's
     arrival buffer before the first event is tight.
   - Prefer hotels at or under budget_max. If none qualify, still
     return the closest-to-budget options and set
     within_budget_available to false rather than hiding the mismatch.
4. If search_hotels returns no usable results at all (e.g. the area is
   sold out for a tournament weekend), call search_hotels_expanded_radius
   instead, set search_scope to 'expanded_radius', and make sure each
   recommendation_note explains the longer commute this creates.
5. Return at most 3 ranked options. Never invent hotels, prices,
   ratings, or distances that didn't come from a tool call.
""",
    tools=[get_trip_requirements, search_hotels, search_hotels_expanded_radius],
    output_schema=HotelRecommendationResponse,
    output_key="hotel_recommendation",
)


# Exposed for mounting under the orchestrator, e.g.:
#   from hotels import hotel_agent
#   orchestrator = Agent(name="orchestrator", sub_agents=[hotel_agent, tournament_agent, ...])
root_agent = hotel_agent


if __name__ == "__main__":
    # Local smoke test via ADK's Runner + in-memory session service.
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