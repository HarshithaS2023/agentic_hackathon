# Twilio SMS Integration Setup Guide

This guide walks you through setting up SMS-based interaction with the orchestrator via Twilio.

## Prerequisites

1. A Twilio account (https://www.twilio.com/console)
2. A Twilio phone number
3. Python 3.8+
4. ngrok (for local testing with public URL)

## Step 1: Install Dependencies

```bash
pip install twilio flask
```

Or use the provided requirements file:

```bash
pip install -r requirements-twilio.txt
```

## Step 2: Get Twilio Credentials

1. Log in to https://www.twilio.com/console
2. Find your **Account SID** and **Auth Token** on the dashboard
3. Note your **Twilio Phone Number** (the one you purchased or will purchase)

## Step 3: Set Environment Variables

Create a `.env` file in the project root:

```bash
export TWILIO_ACCOUNT_SID="your_account_sid_here"
export TWILIO_AUTH_TOKEN="your_auth_token_here"
export TWILIO_PHONE_NUMBER="+1234567890"  # Your Twilio phone number
```

Or set them directly in your shell:

```bash
export TWILIO_ACCOUNT_SID="your_account_sid_here"
export TWILIO_AUTH_TOKEN="your_auth_token_here"
export TWILIO_PHONE_NUMBER="+1234567890"
```

## Step 4: Test Locally with ngrok

### 4a. Start the SMS Server

```bash
python twilio_integration.py
```

The server will start on `http://localhost:5000`

### 4b. Expose to the Internet with ngrok

In a separate terminal:

```bash
ngrok http 5000
```

This gives you a public URL like `https://abc123.ngrok.io`

### 4c. Configure Twilio Webhook

1. Go to https://www.twilio.com/console/phone-numbers/incoming
2. Click on your Twilio phone number
3. Under **Messaging**, set **A MESSAGE COMES IN** webhook to:
   ```
   https://abc123.ngrok.io/sms
   ```
   (Replace `abc123` with your ngrok subdomain)
4. Make sure the method is **HTTP POST**
5. Save

## Step 5: Test the Integration

Text your Twilio phone number with a message like:

```
Find me a tournament
```

or

```
Search for hotels in New York for next week
```

The orchestrator will respond via SMS!

## Example Interactions

### Find a Tournament

**User:** "Find me a tournament"
**Orchestrator:** "I found 3 tournaments matching your profile. The top recommendation is..."

### Book a Hotel

**User:** "Search hotels near Austin, check-in September 5"
**Orchestrator:** "I found 4 hotels near the venue. Here are your options..."

### Book a Flight

**User:** "Find flights from NYC to Miami Sept 1-5"
**Orchestrator:** "Searching flights for you..."

### Confirmation Flow

**User:** "Find me a tournament"
**Orchestrator:** "I recommend the Austin Open on Sept 29. Type YES to confirm."
**User:** "YES"
**Orchestrator:** "✓ Confirmed! Receipt emailed. Added to your calendar."

## Production Deployment

For production, use a proper ASGI server:

```bash
pip install gunicorn eventlet

gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:5000 twilio_integration:app
```

Then deploy to:
- AWS Lambda (with API Gateway)
- Google Cloud Run
- Heroku
- DigitalOcean App Platform
- Your own VPS/server

Update your Twilio webhook URL to point to your production domain.

## Troubleshooting

### "Invalid Twilio request signature"

- Double-check your Auth Token is correct
- Ensure your Twilio webhook URL matches exactly (including protocol)
- Verify ngrok is still running

### "Missing Twilio credentials"

- Ensure environment variables are set correctly
- Use `echo $TWILIO_ACCOUNT_SID` to verify they're exported
- Restart your terminal/server after setting env vars

### Messages not being received

1. Check ngrok logs for webhook calls
2. Check orchestrator logs for errors
3. Verify Twilio webhook URL is correct
4. Make sure your Twilio account has SMS permissions

### Session not persisting

Sessions are stored in-memory. For production with multiple workers, use:
- Redis for session storage
- Firestore (already used by orchestrator)
- Google Cloud Memorystore

See `twilio_integration.py` for the `USER_SESSIONS` dict that can be replaced with a production-ready storage backend.

## Architecture

```
SMS from User
     ↓
Twilio Webhook → /sms endpoint
     ↓
validate_twilio_request() [security check]
     ↓
get_or_create_session() [per phone number]
     ↓
send_message_to_orchestrator() [LLM routing]
     ↓
orchestrator agent routes to:
   - tournament_agent
   - hotel_agent
   - flight_agent
   - confirmation handlers
     ↓
send_sms_response() [reply via SMS]
     ↓
Response to User
```

## Next Steps

1. Wire up real data sources (Firestore for tournaments, hotels, flights)
2. Replace stub calendar/email functions in `orchestrator.py`
3. Set up Redis/Memorystore for session storage
4. Configure rate limiting to prevent abuse
5. Add SMS history logging for analytics
6. Implement conversation timeout (auto-clear old sessions)
7. Add support for multimedia (MMS) for photos/confirmations
