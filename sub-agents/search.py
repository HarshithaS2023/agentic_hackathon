"""
tournament_search_agent.py — Dashboard-only tournament discovery via
Google Search grounding (Google ADK)

WHEN THIS RUNS: only when a player is actively at the dashboard and
clicks something like "Find Tournaments" (e.g. their weekly Monday
check-in). This is NOT wired into the SMS/orchestrator flow, and
should never be triggered by a background job or a scheduled task.

WHY: Gemini's Google Search grounding tool requires displaying
Google's "Search Suggestions" UI to the person who triggered the
search (see the Grounding with Google Search usage terms). SMS has no
surface to render that on, so grounded search is only ever invoked
from a request that's actively rendering the dashboard at that moment.
tournaments.py (the SMS-facing agent) never uses this — it only reads
the `tournaments` Firestore collection this pipeline writes into.

WHY TWO AGENTS INSTEAD OF ONE: the Gemini API does not support
combining search tools (google_search) with function-calling tools in
the same request. ADK's own output_schema-with-tools compatibility
shim works by adding a `set_model_response` function tool when
needed — which would itself violate that restriction if combined with
google_search. So this is deliberately split into a SequentialAgent
with two steps instead of one Agent with both a search tool and an
output_schema:

  1. search_step  — ONLY tool is google_search. No output_schema.
     Produces a plain-text, cited summary of what it found.
  2. extraction_step — NO tools. Has output_schema. Reads step 1's
     text (via ADK's {state_key} instruction templating, keyed by
     search_step's output_key) and structures it into JSON.

Persistence happens in after_agent_callback on the pipeline, as plain
Python — not as a tool call — since a Firestore-write tool can't be
mixed into the search_step either, for the same reason as above.
"""

from __future__ import annotations

import datetime as dt
import sys
import uuid
from pathlib import Path
from typing import Literal

from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import google_search
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_store

MODEL = "gemini-3.6-flash"


# ---------------------------------------------------------------------------
# Structured output schema (produced by the extraction step only)
# ---------------------------------------------------------------------------

class GroundedTournamentResult(BaseModel):
    name: str
    sport: str = Field(description="e.g. 'Tennis', 'Pickleball', 'Basketball'")
    level: str = Field(description="e.g. 'Futures', 'Challenger', 'Local Open', if known")
    date: str = Field(description="ISO date if known, otherwise best available date text")
    location: str
    source_url: str = Field(description="The page this result was grounded on")
    confidence: Literal["high", "medium", "low"] = Field(
        description="How confident the extraction is that these details are accurate and current"
    )


class GroundedSearchResponse(BaseModel):
    results: list[GroundedTournamentResult]
    search_queries_used: list[str] = Field(
        description="The queries Google Search actually ran, for the audit/history log"
    )
    summary: str = Field(description="Plain-language summary for the player")


# ---------------------------------------------------------------------------
# Step 1 — search only, no schema, no other tools
# ---------------------------------------------------------------------------

search_step = Agent(
    name="tournament_search_step",
    model=MODEL,
    description="Runs a live Google Search for current real tournaments matching the player's criteria.",
    instruction="""
You are triggered by a player who is actively looking at their
dashboard right now and asked to find tournaments. The request names a
sport (e.g. tennis, pickleball) plus optionally a location preference
and level — use google_search to find real, currently-listed
tournaments matching all of that criteria.

Write a plain-text summary of what you found. For each tournament,
include: sport, name, level (if stated), date, location, and the URL
you found it on. If you are not confident about a specific date or
level, say so explicitly rather than guessing. Do not invent
tournaments — only report what search results actually show.
""",
    tools=[google_search],
    output_key="raw_search_findings",
)


# ---------------------------------------------------------------------------
# Step 2 — structuring only, no tools, no live search
# ---------------------------------------------------------------------------

extraction_step = Agent(
    name="tournament_search_extraction_step",
    model=MODEL,
    description="Structures the raw search findings into a clean, schema-conformant result.",
    instruction="""
Below are raw findings from a Google Search run a moment ago:

{raw_search_findings}

Convert this into the required structured format. One entry per
distinct tournament found. Set confidence to "low" for anything where
the date or level was unclear or inferred rather than stated outright.
Do not add any tournament that wasn't in the findings above.
""",
    output_schema=GroundedSearchResponse,
    output_key="grounded_search_results",
)


# ---------------------------------------------------------------------------
# Persistence — plain Python, runs after both steps complete
# ---------------------------------------------------------------------------

def _tournament_doc_id(result: dict) -> str:
    """Deterministic id from name+date+location so re-running a search for
    the same tournament upserts instead of creating duplicate rows."""
    key = f"{result['name']}|{result['date']}|{result['location']}".lower().strip()
    return uuid.uuid5(uuid.NAMESPACE_URL, key).hex


def persist_search_results(callback_context: CallbackContext) -> None:
    """Write grounded results to the shared `tournaments` collection and log a
    search_history entry, once both pipeline steps have finished.

    This is NOT a tool the model calls — it's an after_agent_callback,
    plain Python that runs automatically once the SequentialAgent
    finishes. Keeping persistence out of the model's tool-calling loop
    is what lets search_step use google_search without hitting the
    search-tools-cannot-mix-with-function-tools restriction.
    """
    output = callback_context.state.get("grounded_search_results")
    if not output:
        return

    results = output.get("results", [])
    now = dt.datetime.now(dt.timezone.utc)

    # Upsert each result into the shared tournaments store.
    # tournament.py's search_tournaments tool reads from this same store —
    # this is what turns a one-time dashboard search into data the SMS
    # agent can recommend from all week.
    docs = []
    for result in results:
        doc_id = _tournament_doc_id(result)
        docs.append(
            {
                "tournament_id": doc_id,
                "id": doc_id,
                "name": result["name"],
                "sport": result["sport"],
                "level": result["level"],
                "date": result["date"],
                "location": result["location"],
                "source_url": result["source_url"],
                "confidence": result["confidence"],
                "discovered_via": "google_search_grounding",
                "last_seen_at": now.isoformat(),
            }
        )
    if docs:
        data_store.add_tournaments(docs)

    # Append the search_history record — the compliance audit trail
    # confirming a human was present at the dashboard when this grounded
    # search ran (see the module docstring for why that matters).
    data_store.add_search_history(
        {
            "user_id": callback_context.user_id,
            "queries": output.get("search_queries_used", []),
            "result_count": len(results),
            "triggered_at": now.isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

tournament_search_agent = SequentialAgent(
    name="tournament_search_agent",
    description=(
        "Dashboard-only pipeline: runs a live, human-triggered Google Search "
        "for current tournaments, then structures and persists the results."
    ),
    sub_agents=[search_step, extraction_step],
    after_agent_callback=persist_search_results,
)

# Exposed for mounting under a dashboard-facing orchestrator/API layer, e.g.:
#   from tournament_search_agent import tournament_search_agent
#   # only ever call this from a request that is actively rendering the
#   # dashboard's Search Suggestions UI — never from the SMS/orchestrator path.
root_agent = tournament_search_agent


if __name__ == "__main__":
    # Local smoke test via ADK's Runner + in-memory session service.
    # Note: this makes a real Google Search call — only run it with a
    # valid GOOGLE_API_KEY configured.
    import asyncio

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def main() -> None:
        runner = InMemoryRunner(agent=tournament_search_agent, app_name="tournament_search_dev")
        session = await runner.session_service.create_session(
            app_name="tournament_search_dev", user_id="demo_player"
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Find upcoming USTA junior tournaments near San Diego, CA.")],
        )
        async for event in runner.run_async(
            user_id="demo_player", session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)

    asyncio.run(main())