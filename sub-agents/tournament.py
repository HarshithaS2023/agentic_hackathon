"""
tournaments.py — Tournament recommendation sub-agent (Google ADK)

Responsibilities (per architecture):
  - Given a player's ranking + recent match history, find candidate
    tournaments and rank them.
  - If the player has been performing poorly (recent losses, especially
    early-round losses), recommend lower-level events to rebuild
    confidence, or suggest practice matches instead of a tournament.
  - If nothing fits within the initial search window (60 days), widen
    the date range rather than silently returning nothing — mirrors
    the fallback pattern in hotels.py (search_wider_radius) and
    flights.py (search_alternate_airports).
  - Returns structured recommendations only. It does NOT register the
    player, send confirmations, email receipts, or touch the calendar —
    those are orchestrator responsibilities per the confirmation
    state-machine design.

This agent is meant to be mounted as a sub_agent of the orchestrator
agent (see orchestrator.py), which handles session state, the
"Type YES to confirm" flow, and side effects (email, calendar, Firestore
writes to `registrations`).

Note on trip_id: unlike hotels.py/flights.py, this agent is keyed on
player_id, not trip_id. It's the one agent that produces the
information a trip is built from — the orchestrator is expected to
create a `trips` record from the chosen recommendation, which
hotels.py and flights.py then read from. This is intentional, not an
inconsistency to fix.

Data layer notes:
  - `get_player_profile`, `search_tournaments`, and
    `search_wider_date_range` are stubbed here. In production, wire
    them to Firestore (`players`, `tournaments` collections per the
    schema discussed) and to whatever tournament data source you're
    using (scraped feed or an official API).
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

class TournamentRecommendation(BaseModel):
    tournament_id: str
    name: str
    level: str = Field(description="e.g. 'Challenger', 'Futures', 'Local Open'")
    date: str = Field(description="ISO date, e.g. 2026-09-29")
    location: str
    recommendation_note: str = Field(
        description="Why this was recommended given the player's recent form"
    )


class TournamentRecommendationResponse(BaseModel):
    recommendation_type: Literal["tournament", "practice_match"] = Field(
        description=(
            "'practice_match' if recent performance suggests the player "
            "should rebuild form before entering a sanctioned tournament"
        )
    )
    search_scope: Literal["initial_window", "extended_window"] = Field(
        description=(
            "'extended_window' if nothing fit within the initial 60-day "
            "search, requiring a wider date range"
        )
    )
    recommendations: list[TournamentRecommendation]
    reasoning: str = Field(description="Plain-language summary for the player")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_player_profile(player_id: str) -> dict:
    """Fetch a player's ranking and recent match history.

    Args:
        player_id: Unique identifier for the player (e.g. phone number
            used as the Firestore doc id).

    Returns:
        A dict with 'ranking', 'recent_matches' (list of results with
        opponent level and date), and 'location_pref'.
    """
    # TODO: replace with a real Firestore read, e.g.
    #   db.collection("players").document(player_id).get().to_dict()
    return {
        "ranking": 842,
        "recent_matches": [
            {"date": "2026-08-10", "result": "L", "round": "R1", "opponent_level": "Challenger"},
            {"date": "2026-07-28", "result": "L", "round": "R1", "opponent_level": "Challenger"},
            {"date": "2026-07-12", "result": "W", "round": "QF", "opponent_level": "Futures"},
        ],
        "location_pref": "San Diego, CA",
    }


def search_tournaments(location: str, level: str, date_range_days: int = 60) -> list[dict]:
    """Search for upcoming tournaments matching a location and level.

    Args:
        location: City/region to search near.
        level: Target competition level (e.g. 'Futures', 'Challenger',
            'Local Open').
        date_range_days: How many days out to search.

    Returns:
        A list of candidate tournament dicts with id, name, level,
        date, and location.
    """
    # TODO: replace with a real query against your synced `tournaments`
    # collection (populated by a periodic scrape/API sync job, not
    # queried live from an external source on every call).
    return [
        {
            "tournament_id": "sd-open-2026-09",
            "name": "San Diego Open",
            "level": "Futures",
            "date": "2026-09-29",
            "location": "Barnes Tennis Center, San Diego, CA",
        },
        {
            "tournament_id": "socal-challenger-2026-10",
            "name": "SoCal Challenger",
            "level": "Challenger",
            "date": "2026-10-14",
            "location": "Carson, CA",
        },
    ]


def search_wider_date_range(location: str, level: str, date_range_days: int = 120) -> list[dict]:
    """Search for tournaments over a wider date range.

    Used when search_tournaments returns nothing within the initial
    60-day window — common for less common levels/locations where
    events are sparser.

    Args:
        location: City/region to search near.
        level: Target competition level.
        date_range_days: Widened search horizon, in days.

    Returns:
        A list of candidate tournament dicts, same shape as
        search_tournaments.
    """
    # TODO: wire to the same data source as search_tournaments, with a
    # larger date_range_days passed through to the underlying query.
    return [
        {
            "tournament_id": "desert-classic-2026-12",
            "name": "Desert Classic",
            "level": "Futures",
            "date": "2026-12-05",
            "location": "Palm Springs, CA",
        },
    ]


def find_practice_matches(location: str) -> list[dict]:
    """Find informal practice-match opportunities near a location.

    Used when recent performance suggests the player should rebuild
    confidence before entering a sanctioned tournament.

    Args:
        location: City/region to search near.

    Returns:
        A list of practice hitting-partner or practice-match listings.
    """
    # TODO: wire to a real practice-partner board / club API if available.
    return [
        {"listing_id": "practice-sd-1", "detail": "Open hitting session, Barnes Center, Tue/Thu evenings"},
        {"listing_id": "practice-sd-2", "detail": "Club ladder practice matches, La Jolla Tennis Club"},
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

tournament_agent = Agent(
    name="tournament_agent",
    model=MODEL,
    description=(
        "Recommends tournaments (or practice matches) for a player based on "
        "their ranking and recent match performance."
    ),
    instruction="""
You are the tournament recommendation agent for an athlete logistics
assistant. You are called by an orchestrator agent — you never talk to
the player directly and you never register anyone for anything.

Steps:
1. Call get_player_profile to load the player's ranking and recent
   match history.
2. Evaluate recent form:
   - If the player has lost early rounds (R1/R2) in 2 or more of their
     last 3 matches, treat this as a confidence dip. Prefer a lower
     competition level than their ranking would normally suggest, OR
     recommend practice matches instead of a tournament entirely if
     the losses are recent and severe (e.g. 3+ R1 losses in a row).
   - Otherwise, recommend tournaments at or slightly above their
     current level.
3. Call search_tournaments with the chosen level and the player's
   location preference. If recommending practice instead, call
   find_practice_matches instead and skip the remaining steps.
4. If search_tournaments returns nothing, call search_wider_date_range
   with the same level/location and set search_scope to
   'extended_window'. Call out the longer wait in recommendation_note
   when you do this.
5. Return a TournamentRecommendationResponse. Keep recommendation_note
   and reasoning concrete and specific to the player's actual results —
   never generic filler text.

Never invent tournaments or dates that didn't come from a tool call.
""",
    tools=[get_player_profile, search_tournaments, search_wider_date_range, find_practice_matches],
    output_schema=TournamentRecommendationResponse,
    output_key="tournament_recommendation",
)


# Exposed for mounting under the orchestrator, e.g.:
#   from tournaments import tournament_agent
#   orchestrator = Agent(name="orchestrator", sub_agents=[tournament_agent, ...])
root_agent = tournament_agent


if __name__ == "__main__":
    # Local smoke test via ADK's Runner + in-memory session service.
    import asyncio

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def main() -> None:
        runner = InMemoryRunner(agent=tournament_agent, app_name="tournaments_dev")
        session = await runner.session_service.create_session(
            app_name="tournaments_dev", user_id="demo_player"
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Find me a tournament near San Diego.")],
        )
        async for event in runner.run_async(
            user_id="demo_player", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)

    asyncio.run(main())