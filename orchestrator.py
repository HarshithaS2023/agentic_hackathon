"""
orchestrator.py — Top-level orchestrator agent (Google ADK)

Owns everything the sub-agents deliberately don't:
  - Intent routing to Tournament / Hotel / Flight sub-agents
  - The "Type YES to confirm" state machine (pending_action + TTL)
  - Side effects once confirmed: registration record, calendar event,
    email receipt
  - The 2-day-out reminder text (triggered by the separate scheduler,
    see reminder_job() at the bottom — not run by the LLM loop)

Design choice: sub-agents are mounted as AgentTool, not as ADK
`sub_agents` (which does a full conversational transfer). We want the
orchestrator to stay in control of the turn after a sub-agent
responds, because it's the one responsible for deciding whether to
enter a pending-confirmation state — a plain agent transfer would hand
that responsibility to whichever sub-agent last spoke.

Session state is used for the *short-lived* confirmation record
(pending_action, context, expiry). Durable data — player profile,
match history, confirmed registrations — lives in Firestore via tool
calls, per the schema:

  players:       { user_id, ranking, recent_matches, preferences }
  sessions:      { user_id, pending_action, context, expires_at }  <- this file
  registrations: { registration_id, user_id, tournament_id, status,
                    tournament_date, location, calendar_event_id,
                    email_receipt_sent, reminder_sent }
"""

from __future__ import annotations

import datetime as dt
import sys
import uuid
from pathlib import Path
from typing import Literal

from google.adk.agents import Agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent / "sub-agents"))

import data_store
from tournament import tournament_agent
from hotels import hotel_agent
from flights import flight_agent

MODEL = "gemini-3.6-flash"
CONFIRMATION_TTL_MINUTES = 30


# ---------------------------------------------------------------------------
# Confirmation state machine
# ---------------------------------------------------------------------------

class PendingAction(BaseModel):
    action_type: Literal["confirm_registration", "confirm_hotel", "confirm_flight"]
    context: dict
    created_at: str
    expires_at: str


def set_pending_confirmation(
    action_type: Literal["confirm_registration", "confirm_hotel", "confirm_flight"],
    context: dict,
    tool_context: ToolContext,
) -> dict:
    """Stage an action awaiting the player's explicit YES before executing it.

    Call this instead of directly registering/booking anything. It puts
    the session into a pending-confirmation state; the actual side
    effect only runs once handle_confirmation_reply sees a fresh "YES"
    against this pending action.

    Args:
        action_type: What's awaiting confirmation.
        context: Whatever the eventual side-effect tool needs — e.g.
            {"tournament_id": ..., "tournament_name": ..., "date": ...,
            "location": ...} for a registration.
        tool_context: Injected automatically by ADK; do not pass this.

    Returns:
        A dict confirming the pending state was set, including the
        exact confirmation prompt to show the player.
    """
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(minutes=CONFIRMATION_TTL_MINUTES)
    pending = PendingAction(
        action_type=action_type,
        context=context,
        created_at=now.isoformat(),
        expires_at=expires.isoformat(),
    )
    tool_context.state["pending_action"] = pending.model_dump()
    return {
        "status": "awaiting_confirmation",
        "prompt_for_player": "Type YES to confirm.",
        "expires_at": pending.expires_at,
    }


def handle_confirmation_reply(reply: str, tool_context: ToolContext) -> dict:
    """Check an incoming "YES"/"NO" against the session's pending action.

    Call this whenever the player's message looks like a confirmation
    reply and there might be a pending_action in state. This does NOT
    execute the side effect itself — it validates the reply and, if
    valid, tells you which registration/booking tool to call next with
    the staged context.

    Args:
        reply: The player's raw message text.
        tool_context: Injected automatically by ADK; do not pass this.

    Returns:
        A dict with 'result' of "confirmed", "declined", "expired", or
        "no_pending_action", plus the staged context when confirmed.
    """
    pending = tool_context.state.get("pending_action")
    if not pending:
        return {"result": "no_pending_action"}

    now = dt.datetime.now(dt.timezone.utc)
    expires_at = dt.datetime.fromisoformat(pending["expires_at"])
    if now > expires_at:
        tool_context.state["pending_action"] = None
        return {"result": "expired"}

    normalized = reply.strip().lower()
    if normalized in {"yes", "y", "confirm"}:
        tool_context.state["pending_action"] = None
        return {
            "result": "confirmed",
            "action_type": pending["action_type"],
            "context": pending["context"],
        }
    if normalized in {"no", "n", "cancel"}:
        tool_context.state["pending_action"] = None
        return {"result": "declined"}

    # Ambiguous reply — leave the pending action intact rather than
    # silently dropping it, so a stray unrelated message doesn't
    # cancel a confirmation the player still means to complete.
    return {"result": "unclear", "action_type": pending["action_type"]}


# ---------------------------------------------------------------------------
# Side-effect tools (only ever called after handle_confirmation_reply
# returns "confirmed")
# ---------------------------------------------------------------------------

def register_player_for_tournament(
    user_id: str, tournament_id: str, tournament_name: str, date: str, location: str
) -> dict:
    """Write a confirmed registration and kick off receipt + calendar side effects.

    Only call this after handle_confirmation_reply returned
    result="confirmed" with action_type="confirm_registration".

    Args:
        user_id: The player's id (phone number).
        tournament_id: Id of the tournament being registered for.
        tournament_name: Display name for the receipt/calendar event.
        date: ISO date of the tournament.
        location: Venue/location string.

    Returns:
        The created registration record.
    """
    # TODO: replace with a real Firestore write to `registrations`.
    registration_id = str(uuid.uuid4())
    calendar_event_id = _add_calendar_event(tournament_name, date, location)
    email_sent = _send_email_receipt(user_id, tournament_name, date, location)
    record = {
        "registration_id": registration_id,
        "user_id": user_id,
        "tournament_id": tournament_id,
        "status": "confirmed",
        "tournament_date": date,
        "location": location,
        "calendar_event_id": calendar_event_id,
        "email_receipt_sent": email_sent,
        "reminder_sent": False,
    }
    data_store.add_booking(
        {
            "id": registration_id,
            "user_id": user_id,
            "type": "tournament",
            "title": tournament_name,
            "date": date,
            "location": location,
            "status": "confirmed",
            "confirmation": registration_id[:8],
        }
    )
    return record


def book_hotel(
    user_id: str,
    hotel_id: str,
    hotel_name: str,
    address: str,
    check_in: str,
    check_out: str,
    total_price: float,
) -> dict:
    """Write a confirmed hotel booking and send its receipt.

    Only call this after handle_confirmation_reply returned
    result="confirmed" with action_type="confirm_hotel".

    Args:
        user_id: The player's id (phone number).
        hotel_id: Id of the hotel option being booked.
        hotel_name: Display name for the receipt.
        address: Hotel address string.
        check_in: ISO date of check-in.
        check_out: ISO date of check-out.
        total_price: Total stay price in USD.

    Returns:
        The created booking record.
    """
    booking_id = str(uuid.uuid4())
    email_sent = _send_email_receipt(user_id, hotel_name, check_in, address)
    data_store.add_booking(
        {
            "id": booking_id,
            "user_id": user_id,
            "type": "hotel",
            "title": hotel_name,
            "date": check_in,
            "location": address,
            "status": "confirmed",
            "confirmation": booking_id[:8],
            "reminder_sent": False,
            "check_in": check_in,
            "check_out": check_out,
            "total_price": total_price,
        }
    )
    return {
        "booking_id": booking_id,
        "status": "confirmed",
        "email_receipt_sent": email_sent,
        "check_in": check_in,
        "check_out": check_out,
    }


def book_flight(
    user_id: str,
    flight_id: str,
    airline: str,
    route: str,
    depart_time: str,
    arrive_time: str,
    price: float,
) -> dict:
    """Write a confirmed flight booking and send its receipt.

    Only call this after handle_confirmation_reply returned
    result="confirmed" with action_type="confirm_flight".

    Args:
        user_id: The player's id (phone number).
        flight_id: Id of the flight leg being booked.
        airline: Operating airline name.
        route: Human route string, e.g. "SAN → LAX".
        depart_time: ISO datetime of departure.
        arrive_time: ISO datetime of arrival.
        price: Ticket price in USD.

    Returns:
        The created booking record.
    """
    booking_id = str(uuid.uuid4())
    email_sent = _send_email_receipt(user_id, f"{airline} flight {route}", depart_time, route)
    data_store.add_booking(
        {
            "id": booking_id,
            "user_id": user_id,
            "type": "flight",
            "title": f"{airline} {route}",
            "date": depart_time,
            "location": route,
            "status": "confirmed",
            "confirmation": booking_id[:8],
            "reminder_sent": False,
            "arrive_time": arrive_time,
            "price": price,
        }
    )
    return {
        "booking_id": booking_id,
        "status": "confirmed",
        "email_receipt_sent": email_sent,
    }


def _add_calendar_event(title: str, date: str, location: str) -> str:
    """Add an event to the player's Google Calendar. Returns the event id."""
    # TODO: real Google Calendar API call (google-api-python-client +
    # service-account creds). Stubbed to a synthetic id + a log line so the
    # rest of the confirmation flow is observable end-to-end in dev.
    event_id = f"cal_event_{uuid.uuid4().hex[:8]}"
    print(f"[calendar] created {event_id}: {title} on {date} @ {location}")
    return event_id


def _send_email_receipt(user_id: str, item_name: str, date: str, location: str) -> bool:
    """Send a booking receipt email. Returns whether it sent successfully."""
    # TODO: real SendGrid/SMTP call. Stubbed to a log line for now.
    print(f"[email] receipt -> {user_id}: {item_name} ({date}, {location})")
    return True


# ---------------------------------------------------------------------------
# Orchestrator agent
# ---------------------------------------------------------------------------

orchestrator = Agent(
    name="orchestrator",
    model=MODEL,
    description="Top-level assistant that routes player requests to booking sub-agents and owns confirmations.",
    instruction="""
You are an athlete logistics assistant reachable over SMS/iMessage.
Replies are texted to the player, so keep them short and plain — no
markdown, no headers.

Routing:
- Tournament questions ("find me a tournament", "what should I play
  next") -> call the tournament_agent tool.
- Hotel questions -> call the hotel_agent tool.
- Flight questions -> call the flight_agent tool.

Confirmation flow (you own this, sub-agents never touch it):
- Before registering a player for a tournament, booking a hotel, or
  booking a flight, call set_pending_confirmation with the relevant
  context and send the player a short summary ending in
  "Type YES to confirm."
- On every incoming message, if it looks like it could be a yes/no
  reply, call handle_confirmation_reply first.
  - result="confirmed" and action_type="confirm_registration" ->
    call register_player_for_tournament with the staged context, then
    tell the player it's booked, the receipt is emailed, and it's on
    their calendar.
  - result="confirmed" and action_type="confirm_hotel" -> call
    book_hotel with the staged context, then tell the player the room
    is booked and the receipt is emailed.
  - result="confirmed" and action_type="confirm_flight" -> call
    book_flight with the staged context, then tell the player the
    flight is booked and the receipt is emailed.
  - result="declined" -> acknowledge and stop, do not book anything.
  - result="expired" -> tell the player the confirmation window
    closed and ask if they'd like to redo it.
  - result="no_pending_action" -> there's nothing to confirm; treat
    the message as a normal new request instead.
  - result="unclear" -> ask them to reply YES or NO.

Never call a registration or booking tool without a prior
"confirmed" result from handle_confirmation_reply. This is a hard
rule, not a suggestion.
""",
    tools=[
        AgentTool(agent=tournament_agent),
        AgentTool(agent=hotel_agent),
        AgentTool(agent=flight_agent),
        set_pending_confirmation,
        handle_confirmation_reply,
        register_player_for_tournament,
        book_hotel,
        book_flight,
    ],
)

root_agent = orchestrator


# ---------------------------------------------------------------------------
# Scheduler entry point — NOT part of the LLM conversation loop.
# Invoke this from a cron job / Cloud Scheduler hitting a Cloud Run
# endpoint, roughly once a day. It queries Firestore directly and
# sends plain templated texts — no need to route this through the
# agent since there's no judgment call to make, just a lookup + send.
# ---------------------------------------------------------------------------

REMINDER_LEAD_DAYS = 2


def _send_reminder_text(user_id: str, title: str, date: str, location: str) -> bool:
    """Send the "2 days out" reminder SMS. Returns whether it sent."""
    # TODO: real Twilio send. Stubbed to a log line for now.
    print(
        f"[reminder] -> {user_id}: {title} in {REMINDER_LEAD_DAYS} days "
        f"({date}, {location})"
    )
    return True


def reminder_job() -> dict:
    """Send "2 days out" reminder texts for upcoming confirmed registrations.

    Reads confirmed bookings from data_store (the stand-in for the
    Firestore `registrations` collection), sends a reminder for any whose
    date is exactly REMINDER_LEAD_DAYS out and that hasn't been reminded
    yet, then flips reminder_sent=True on each. Idempotent by design:
    safe to run more than once a day without double-sending.

    Returns a small summary dict so a cron/Cloud Scheduler caller can log
    what happened.

    TODO: when Firestore is live this becomes:
        db.collection("registrations")
          .where("status", "==", "confirmed")
          .where("reminder_sent", "==", False).stream()
    with the same date filter + Twilio send + reminder_sent flip.
    """
    today = dt.date.today()
    checked = 0
    sent = 0
    for booking in data_store.list_bookings():
        if booking.get("status") != "confirmed" or booking.get("reminder_sent"):
            continue
        checked += 1
        raw_date = (booking.get("date") or "")[:10]
        try:
            event_date = dt.date.fromisoformat(raw_date)
        except ValueError:
            continue
        if (event_date - today).days != REMINDER_LEAD_DAYS:
            continue
        if _send_reminder_text(
            booking.get("user_id", ""),
            booking.get("title", "your event"),
            raw_date,
            booking.get("location", ""),
        ):
            data_store.mark_reminder_sent(booking["id"])
            sent += 1
    return {"checked": checked, "reminders_sent": sent}


if __name__ == "__main__":
    import asyncio

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def main() -> None:
        runner = InMemoryRunner(agent=orchestrator, app_name="orchestrator_dev")
        session = await runner.session_service.create_session(
            app_name="orchestrator_dev", user_id="demo_player"
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