"""
twilio_integration.py — Twilio SMS webhook handler for the orchestrator

Responsibilities:
  - Accept incoming SMS via Twilio webhook
  - Route messages to the orchestrator agent
  - Maintain user sessions per phone number
  - Send orchestrator responses back via SMS
  - Handle Twilio request validation

Setup:
  1. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER env vars
  2. Configure Twilio webhook URL to point to POST /sms endpoint
  3. Run: python -m flask --app twilio_integration run
  4. Expose to internet (e.g. ngrok) and update Twilio dashboard
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from flask import Flask, request
from twilio.rest import Client
from twilio.request_validator import RequestValidator

from orchestrator import orchestrator
from google.adk.runners import InMemoryRunner
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Twilio credentials (load from environment variables)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    logger.warning(
        "Missing Twilio credentials. Set TWILIO_ACCOUNT_SID, "
        "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables."
    )

# Initialize Twilio client and request validator
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
validator = RequestValidator(TWILIO_AUTH_TOKEN)

# Flask app
app = Flask(__name__)

# In-memory session storage (in production, use Redis or Firestore)
# Maps phone_number -> runner and session_id for conversational state
USER_SESSIONS: dict[str, dict] = {}

# Maximum message length for SMS (accounting for Twilio's limits)
MAX_SMS_LENGTH = 1600


async def get_or_create_session(phone_number: str) -> tuple[InMemoryRunner, str]:
    """Get an existing session for a user or create a new one.
    
    Args:
        phone_number: The user's phone number (from Twilio).
        
    Returns:
        A tuple of (runner, session_id) for this user.
    """
    if phone_number in USER_SESSIONS:
        return (
            USER_SESSIONS[phone_number]["runner"],
            USER_SESSIONS[phone_number]["session_id"],
        )

    # Create a new session
    runner = InMemoryRunner(agent=orchestrator, app_name="orchestrator_sms")
    session = await runner.session_service.create_session(
        app_name="orchestrator_sms",
        user_id=phone_number,
    )

    USER_SESSIONS[phone_number] = {
        "runner": runner,
        "session_id": session.session_id,
    }

    logger.info(f"Created new session for {phone_number}: {session.session_id}")
    return runner, session.session_id


async def send_message_to_orchestrator(
    phone_number: str, message_text: str
) -> Optional[str]:
    """Send a message to the orchestrator and get a response.
    
    Args:
        phone_number: The user's phone number.
        message_text: The user's message.
        
    Returns:
        The orchestrator's response text, or None if an error occurred.
    """
    try:
        runner, session_id = await get_or_create_session(phone_number)

        # Create a content message
        user_message = types.Content(parts=[types.TextPart(text=message_text)])

        # Send the message to the orchestrator
        response = await runner.send_message(
            app_name="orchestrator_sms",
            user_id=phone_number,
            message=user_message,
        )

        # Extract text from the response
        response_text = ""
        if response.message and response.message.parts:
            for part in response.message.parts:
                if hasattr(part, "text"):
                    response_text += part.text

        return response_text if response_text else None

    except Exception as e:
        logger.error(f"Error sending message to orchestrator: {e}", exc_info=True)
        return None


def split_message_if_needed(text: str) -> list[str]:
    """Split a message into SMS-friendly chunks if needed.
    
    Args:
        text: The text to potentially split.
        
    Returns:
        A list of message chunks, each under MAX_SMS_LENGTH.
    """
    if len(text) <= MAX_SMS_LENGTH:
        return [text]

    chunks = []
    words = text.split()
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 > MAX_SMS_LENGTH:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = word
        else:
            current_chunk += f" {word}" if current_chunk else word

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def send_sms_response(to_number: str, message_text: str) -> bool:
    """Send an SMS response via Twilio.
    
    Args:
        to_number: Recipient's phone number.
        message_text: Message text to send.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        # Split message if needed
        chunks = split_message_if_needed(message_text)

        for chunk in chunks:
            twilio_client.messages.create(
                body=chunk,
                from_=TWILIO_PHONE_NUMBER,
                to=to_number,
            )
            logger.info(f"Sent SMS to {to_number}: {chunk[:50]}...")

        return True

    except Exception as e:
        logger.error(f"Error sending SMS to {to_number}: {e}", exc_info=True)
        return False


def validate_twilio_request(request_obj) -> bool:
    """Validate that a request actually came from Twilio.
    
    Args:
        request_obj: Flask request object.
        
    Returns:
        True if the request is valid, False otherwise.
    """
    # Get the X-Twilio-Signature header
    twilio_signature = request_obj.headers.get("X-Twilio-Signature", "")

    # Construct the full URL with query params
    url = request_obj.url

    # Validate
    return validator.validate(url, request_obj.form, twilio_signature)


@app.route("/sms", methods=["POST"])
def handle_sms_webhook():
    """Handle incoming SMS webhooks from Twilio."""
    # Validate the request came from Twilio
    if not validate_twilio_request(request):
        logger.warning("Invalid Twilio request signature")
        return "Unauthorized", 403

    # Extract message details
    from_number = request.form.get("From", "")
    message_body = request.form.get("Body", "").strip()
    message_sid = request.form.get("MessageSid", "")

    logger.info(f"Received SMS from {from_number} (SID: {message_sid}): {message_body}")

    if not message_body:
        logger.warning("Empty message body received")
        return "OK", 200

    # Process the message asynchronously
    try:
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response_text = loop.run_until_complete(
            send_message_to_orchestrator(from_number, message_body)
        )
        loop.close()

        if response_text:
            send_sms_response(from_number, response_text)
        else:
            send_sms_response(
                from_number,
                "Sorry, I encountered an error. Please try again.",
            )

    except Exception as e:
        logger.error(f"Error processing SMS: {e}", exc_info=True)
        send_sms_response(
            from_number,
            "Sorry, something went wrong. Please try again later.",
        )

    return "OK", 200


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}, 200


@app.route("/", methods=["GET"])
def index():
    """Root endpoint."""
    return {
        "service": "Orchestrator SMS Gateway",
        "endpoints": {
            "sms_webhook": "POST /sms",
            "health": "GET /health",
        },
    }, 200


if __name__ == "__main__":
    # Note: For production, use a proper ASGI server like gunicorn + eventlet
    # Example: gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:5000 twilio_integration:app
    app.run(debug=True, host="0.0.0.0", port=5000)
