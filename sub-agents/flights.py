"""
flights.py — Flight search sub-agent (Google ADK)

Same shape and rules as tournaments.py / hotels.py:
  - Search/recommend only. No booking, no payment, no side effects.
  - Called by the orchestrator via AgentTool, not talked to directly
    by the player.
  - Actual booking only happens after the orchestrator runs its
    confirmation state machine.

Data layer notes:
  - get_player_travel_profile and search_flights are stubbed. Wire
    get_player_travel_profile to Firestore (`players.home_airport`,
    `players.preferences`) and search_flights to a real flight search
    API (e.g. Amadeus Flight Offers Search, Duffel) once you have keys.
"""

from __future__ import annotations

from google.adk.agents import Agent
from pydantic import BaseModel, Field

MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class FlightOption(BaseModel):
    flight_id: str
    airline: str
    price: float
    depart_time: str = Field(description="ISO datetime")
    arrival_time: str = Field(description="ISO datetime")
    stops: int


class FlightSearchResponse(BaseModel):
    options: list[FlightOption]
    reasoning: str = Field(description="Plain-language summary for the player")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_player_travel_profile(player_id: str) -> dict:
    """Fetch a player's travel-relevant profile info.

    Args:
        player_id: Unique identifier for the player (e.g. phone number
            used as the Firestore doc id).

    Returns:
        A dict with 'home_airport' and any seating/airline preferences.
    """
    # TODO: replace with a real Firestore read from `players`.
    return {"home_airport": "SAN", "seat_pref": "aisle"}


def search_flights(origin: str, destination: str, depart_date: str, return_date: str) -> list[dict]:
    """Search for round-trip flight options.

    Args:
        origin: Origin airport code, e.g. 'SAN'.
        destination: Destination airport code, e.g. 'LAX'.
        depart_date: ISO date of outbound flight.
        return_date: ISO date of return flight.

    Returns:
        A list of candidate flight dicts with id, airline, price,
        depart_time, arrival_time, and stops.
    """
    # TODO: replace with a real call to a flight search API.
    return [
        {
            "flight_id": "aa-1123",
            "airline": "American Airlines",
            "price": 214.50,
            "depart_time": f"{depart_date}T07:15:00",
            "arrival_time": f"{depart_date}T08:40:00",
            "stops": 0,
        },
        {
            "flight_id": "dl-887",
            "airline": "Delta",
            "price": 189.00,
            "depart_time": f"{depart_date}T11:05:00",
            "arrival_time": f"{depart_date}T13:10:00",
            "stops": 1,
        },
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

flight_agent = Agent(
    name="flight_agent",
    model=MODEL,
    description="Searches flight options for a tournament trip.",
    instruction="""
You are the flight search agent for an athlete logistics assistant.
You are called by an orchestrator agent — you never talk to the player
directly and you never book anything.

Steps:
1. Call get_player_travel_profile to load the player's home airport
   and preferences.
2. Call search_flights using the player's home airport as origin, the
   tournament location's nearest airport as destination, and the
   relevant travel dates.
3. Return a FlightSearchResponse with 2-4 ranked options and a short
   reasoning string (e.g. tradeoff between price and stops/timing).

Never invent flights, prices, or times that didn't come from a tool
call.
""",
    tools=[get_player_travel_profile, search_flights],
    output_schema=FlightSearchResponse,
    output_key="flight_recommendation",
)

root_agent = flight_agent


if __name__ == "__main__":
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
            parts=[types.Part(text="Find me a flight to San Diego for Sept 28.")],
        )
        async for event in runner.run_async(
            user_id="demo_player", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)

    asyncio.run(main())