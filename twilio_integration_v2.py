"""
twilio_integration_v2.py — Enhanced Twilio SMS webhook handler with session management

This is the production-ready version that uses SessionManager for better scalability.

Responsibilities:
  - Accept incoming SMS via Twilio webhook
  - Maintain persistent user sessions (supports in-memory, Redis, Firestore)
  - Route messages to the orchestrator agent
  - Send orchestrator responses back via SMS
  - Handle Twilio request validation
  - Automatic session cleanup

Setup:
  1. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER env vars
  2. (Optional) Set REDIS_URL or GOOGLE_CLOUD_PROJECT for production sessions
  3. Configure Twilio webhook URL to point to POST /sms endpoint
  4. Run: gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:5000 twilio_integration_v2:app
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from flask import Flask, request
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from google.genai import types

from orchestrator import orchestrator
from session_manager import SessionManager, UserSession

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

# Initialize session manager (auto-detects backend: memory → redis → firestore)
session_manager = SessionManager.create()

# Flask app
app = Flask(__name__)

# Maximum message length for SMS
MAX_SMS_LENGTH = 1600


async def send_message_to_orchestrator(
    session: UserSession, message_text: str
) -> Optional[str]:
    """Send a message to the orchestrator and get a response.
    
    Args:
        session: The UserSession.
        message_text: The user's message.
        
    Returns:
        The orchestrator's response text, or None if an error occurred.
    """
    try:
        # Create a content message
        user_message = types.Content(parts=[types.TextPart(text=message_text)])

        # Send the message to the orchestrator
        response = await session.runner.send_message(
            app_name="orchestrator_sms",
            user_id=session.phone_number,
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
        logger.error(
            f"Error sending message to orchestrator for {session.phone_number}: {e}",
            exc_info=True,
        )
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
        
        async def process_message():
            # Get or create session
            session = await session_manager.get_or_create(from_number)
            
            # Send to orchestrator
            response_text = await send_message_to_orchestrator(session, message_body)
            
            # Save session state
            await session_manager.save_session(session)
            
            return response_text
        
        response_text = loop.run_until_complete(process_message())
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
    return {"status": "healthy", "backend": type(session_manager.backend).__name__}, 200


@app.route("/sessions/cleanup", methods=["POST"])
def cleanup_sessions():
    """Manual endpoint to trigger session cleanup (can be called by cron)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        count = loop.run_until_complete(session_manager.cleanup_expired_sessions())
        loop.close()
        
        return {
            "status": "success",
            "sessions_cleaned": count,
        }, 200
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


@app.route("/", methods=["GET"])
def index():
    """Root endpoint."""
    return {
        "service": "Orchestrator SMS Gateway (v2)",
        "backend": type(session_manager.backend).__name__,
        "endpoints": {
            "sms_webhook": "POST /sms",
            "health": "GET /health",
            "cleanup": "POST /sessions/cleanup",
        },
    }, 200


if __name__ == "__main__":
    # Development only
    app.run(debug=True, host="0.0.0.0", port=5000)
