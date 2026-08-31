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
  - `get_player_profile` is still stubbed — wire it to Firestore
    (`players` collection) when ready.
  - `search_tournaments` and `search_wider_date_range` read from the
    shared `tournaments` Firestore collection, which is populated by
    tournament_search_agent.py's dashboard-triggered Google Search
    grounding pipeline (see that file for why discovery happens there
    and not here — USTA/TennisLink prohibit scraping in their terms,
    so this agent never fetches tournament data itself; it only reads
    what's already been discovered and persisted).
  - Keep these as plain functions decorated as ADK tools — ADK reads
    the function signature + docstring to build the tool schema, so
    keep type hints and docstrings accurate.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from typing import Literal

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search
from google.genai import types as genai_types
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_store

MODEL = "gemini-3.6-flash"


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
    # Reads the shared `players` store (data_store.py stands in for the
    # Firestore `players` collection until GCP credentials are wired up —
    # swap the body of data_store.get_player for a real
    #   db.collection("players").document(player_id).get().to_dict()
    # then). Falls back to a demo profile for an unknown id, mirroring the
    # get_trip() fallback in hotels.py / flights.py so the __main__ smoke
    # test and un-provisioned players still exercise the full flow.
    player = data_store.get_player(player_id)
    if player:
        return {
            "ranking": player.get("ranking"),
            "recent_matches": player.get("recent_matches", []),
            "location_pref": player.get("location_pref", ""),
        }
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

    Reads from the shared `tournaments` Firestore collection — the same
    collection tournament_search_agent.py's dashboard-triggered pipeline
    writes into. This function never calls a live search or scraper
    itself; it only queries what's already been discovered and persisted.

    Args:
        location: City/region to search near.
        level: Target competition level (e.g. 'Futures', 'Challenger',
            'Local Open').
        date_range_days: How many days out to search.

    Returns:
        A list of candidate tournament dicts with id, name, level,
        date, and location.
    """
    cutoff_date = (dt.date.today() + dt.timedelta(days=date_range_days)).isoformat()
    today = dt.date.today().isoformat()
    location_lower = location.lower()

    # Location is filtered as a substring match rather than an exact-match
    # clause, since tournament location strings are free text (e.g.
    # "Barnes Tennis Center, San Diego, CA") and a substring/region match
    # is more useful here.
    results = [
        t
        for t in data_store.list_tournaments()
        if t.get("level") == level
        and today <= t.get("date", "") <= cutoff_date
        and location_lower in t.get("location", "").lower()
    ]
    results.sort(key=lambda t: t.get("date", ""))
    return results[:10]


def search_wider_date_range(location: str, level: str, date_range_days: int = 120) -> list[dict]:
    """Search for tournaments over a wider date range.

    Used when search_tournaments returns nothing within the initial
    60-day window — common for less common levels/locations where
    events are sparser. Same Firestore collection, wider date filter.

    Args:
        location: City/region to search near.
        level: Target competition level.
        date_range_days: Widened search horizon, in days.

    Returns:
        A list of candidate tournament dicts, same shape as
        search_tournaments.
    """
    return search_tournaments(location, level, date_range_days=date_range_days)


_PRACTICE_FALLBACK = [
    {"listing_id": "practice-sd-1", "detail": "Open hitting session, Barnes Center, Tue/Thu evenings"},
    {"listing_id": "practice-sd-2", "detail": "Club ladder practice matches, La Jolla Tennis Club"},
]

# A search-only helper agent. Unlike USTA/TennisLink tournament data (which
# tournaments.py is barred from fetching itself — see the module docstring),
# public hitting sessions / club ladders / "find a hitting partner" boards
# are fine to look up live, so this stub is wired to Google Search grounding
# rather than a hardcoded list. It's a separate single-tool agent because
# Gemini won't combine google_search with function tools or an output_schema
# in one request (same constraint search.py splits its pipeline around).
_practice_search_agent = Agent(
    name="practice_match_search_step",
    model=MODEL,
    description="Runs a live Google Search for public practice-match / hitting opportunities near a location.",
    instruction="""
Given a location, use google_search to find real, currently-listed ways
for a competitive tennis player to get practice reps in near it:
public/open hitting sessions, club ladders, drop-in clinics, adult
practice groups, or "find a hitting partner" boards.

Reply as a plain-text list, one option per line, each line starting with
"- " in the form:
- <venue or group name> — <what it is, schedule if stated> — <URL>
Only list what the search results actually show. Do not invent venues.
""",
    tools=[google_search],
    output_key="practice_findings",
)

_PRACTICE_LINE_RE = re.compile(r"^\s*[-*•]\s+(.*\S)")


def _parse_practice_lines(text: str) -> list[dict]:
    """Best-effort scrape of the helper agent's plain-text bullet list."""
    listings: list[dict] = []
    for raw in (text or "").splitlines():
        match = _PRACTICE_LINE_RE.match(raw)
        if not match:
            continue
        detail = match.group(1).strip()
        if len(detail) < 8:
            continue
        listings.append({"listing_id": f"practice-{len(listings) + 1}", "detail": detail})
    return listings[:5]


async def find_practice_matches(location: str) -> list[dict]:
    """Find informal practice-match opportunities near a location.

    Used when recent performance suggests the player should rebuild
    confidence before entering a sanctioned tournament. Runs a live
    Google Search (via a dedicated single-tool sub-agent) and parses the
    results; falls back to a small static list if grounded search is
    unavailable (e.g. no Vertex credentials) or returns nothing usable.

    Args:
        location: City/region to search near.

    Returns:
        A list of practice hitting-partner or practice-match listings,
        each a dict with 'listing_id' and 'detail'.
    """
    try:
        runner = InMemoryRunner(agent=_practice_search_agent, app_name="practice_search_dev")
        session = await runner.session_service.create_session(
            app_name="practice_search_dev", user_id="tournament_agent"
        )
        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(
                text=f"Find tennis practice matches and open hitting sessions near {location}."
            )],
        )
        chunks: list[str] = []
        async for event in runner.run_async(
            user_id="tournament_agent", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        chunks.append(part.text)
        listings = _parse_practice_lines("".join(chunks))
    except Exception:  # noqa: BLE001 — grounded search is best-effort here
        listings = []
    return listings or [dict(item) for item in _PRACTICE_FALLBACK]


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