"""
hotels.py — Hotel search sub-agent (Google ADK)

Same shape and rules as tournaments.py:
  - Search/recommend only. No booking, no payment, no side effects.
  - Called by the orchestrator via AgentTool, not talked to directly
    by the player.
  - Actual booking only happens after the orchestrator runs its
    confirmation state machine and calls a booking tool of its own
    (or, once you're past mocks, a real hotel-booking API call).

Data layer notes:
  - get_player_preferences and search_hotels are stubbed. Wire
    get_player_preferences to Firestore (`players.preferences`) and
    search_hotels to a real hotel API (e.g. Booking.com affiliate API,
    Amadeus Hotel Search) once you have keys.
"""

from __future__ import annotations

from google.adk.agents import Agent
from pydantic import BaseModel, Field

MODEL = "gemini-2.5-flash"


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


class HotelSearchResponse(BaseModel):
    options: list[HotelOption]
    reasoning: str = Field(description="Plain-language summary for the player")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_player_preferences(player_id: str) -> dict:
    """Fetch a player's hotel-relevant preferences.

    Args:
        player_id: Unique identifier for the player (e.g. phone number
            used as the Firestore doc id).

    Returns:
        A dict with 'budget_per_night' and any other lodging prefs.
    """
    # TODO: replace with a real Firestore read from `players.preferences`.
    return {"budget_per_night": 150, "prefers_near_venue": True}


def search_hotels(
    location: str, check_in: str, check_out: str, budget_per_night: float
) -> list[dict]:
    """Search for hotels near a location for a given date range and budget.

    Args:
        location: Venue or city to search near.
        check_in: ISO date, e.g. 2026-09-28.
        check_out: ISO date, e.g. 2026-09-30.
        budget_per_night: Max price per night in USD.

    Returns:
        A list of candidate hotel dicts with id, name, address,
        price_per_night, total_price, and distance_note.
    """
    # TODO: replace with a real call to a hotel search API.
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


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

hotel_agent = Agent(
    name="hotel_agent",
    model=MODEL,
    description="Searches hotel options near a tournament location and date range.",
    instruction="""
You are the hotel search agent for an athlete logistics assistant. You
are called by an orchestrator agent — you never talk to the player
directly and you never book anything.

Steps:
1. Call get_player_preferences to load the player's budget and lodging
   preferences.
2. Call search_hotels with the tournament location, check-in/check-out
   dates, and the player's budget_per_night.
3. Return a HotelSearchResponse with 2-4 ranked options and a short
   reasoning string (e.g. why the top option was ranked first —
   distance, price, or both).

Never invent hotels, prices, or addresses that didn't come from a tool
call.
""",
    tools=[get_player_preferences, search_hotels],
    output_schema=HotelSearchResponse,
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
            parts=[types.Part(text="Find me a hotel near Barnes Tennis Center for Sept 28-30.")],
        )
        async for event in runner.run_async(
            user_id="demo_player", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)

    asyncio.run(main())