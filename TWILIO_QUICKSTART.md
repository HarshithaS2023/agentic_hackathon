# Twilio SMS Integration Quick Start

This guide explains how to integrate Twilio SMS with your orchestrator.

## What This Does

When someone texts your Twilio number with a request like:
- "Find me a tournament"
- "Search hotels in Austin"
- "Book a flight to Miami"

The orchestrator will:
1. **Route** to the appropriate sub-agent (tournaments, hotels, flights)
2. **Search** for options based on the user's profile and request
3. **Confirm** before booking (asks for "YES" to confirm)
4. **Execute** the booking and send confirmations via email/calendar
5. **Respond** via SMS with results

## Quick Start (5 minutes)

### 1. Get Twilio Credentials
- Go to https://www.twilio.com/console
- Copy your Account SID and Auth Token
- Buy a phone number (e.g., +1-XXX-XXX-XXXX)

### 2. Install Dependencies
```bash
pip install -r requirements-twilio.txt
```

### 3. Set Environment Variables
```bash
export TWILIO_ACCOUNT_SID="your_account_sid"
export TWILIO_AUTH_TOKEN="your_auth_token"
export TWILIO_PHONE_NUMBER="+1234567890"
```

### 4. Run Locally (Development)
```bash
python twilio_integration.py
```

### 5. Expose to Internet (for Twilio webhooks)
```bash
# In another terminal
ngrok http 5000
# You'll get a URL like: https://abc123.ngrok.io
```

### 6. Configure Twilio Webhook
1. Go to https://www.twilio.com/console/phone-numbers/incoming
2. Click your phone number
3. Under "Messaging" → "A MESSAGE COMES IN", set to:
   ```
   https://abc123.ngrok.io/sms
   ```
4. Save

### 7. Test!
Text your Twilio number with: "Find me a tournament"

## File Structure

```
agentic_hackathon/
├── orchestrator.py              # Main orchestrator agent
├── flights.py                   # Flight sub-agent
├── sub-agents/
│   ├── flights.py              # Detailed flight agent
│   ├── hotels.py               # Hotel agent
│   └── tournament.py           # Tournament agent
├── twilio_integration.py         # Basic Twilio handler (dev)
├── twilio_integration_v2.py      # Production Twilio handler
├── session_manager.py            # Session storage abstraction
├── TWILIO_SETUP.md              # Detailed setup guide
├── DEPLOYMENT.md                # Production deployment guide
├── requirements-twilio.txt      # Dependencies
├── setup_twilio.sh              # Automated setup script
└── .env.example                 # Environment variables template
```

## Key Components

### Orchestrator Agent
Handles:
- Intent routing (tournament/hotel/flight requests)
- Confirmation flow ("Type YES to confirm")
- Session state management
- Side effects (calendar, email, registrations)

### Session Manager
Provides flexible session storage:
- **In-memory** (development only)
- **Redis** (recommended for production)
- **Firestore** (scalable, integrated with orchestrator)

### Twilio Integration
Two versions:
- `twilio_integration.py` - Basic, in-memory sessions (dev)
- `twilio_integration_v2.py` - Production-ready with session manager

## Features

✅ **Intent Routing** - Automatically routes to correct sub-agent
✅ **Confirmation Flow** - Requires "YES" before executing bookings
✅ **Session Management** - Maintains conversation history per user
✅ **Multi-message Support** - Splits long responses into multiple SMS
✅ **Error Handling** - Graceful error messages to users
✅ **Validation** - Verifies all requests come from Twilio
✅ **Flexible Storage** - Memory/Redis/Firestore backend support
✅ **Production Ready** - Includes deployment guides for major platforms

## Examples

### Find Tournament
```
User:  "Find me a tournament"
Bot:   "Based on your ranking, I recommend the Austin Open (Sept 29). 
        Level: Challenger. Type YES to confirm."
User:  "YES"
Bot:   "✓ Confirmed! Receipt emailed. Added to your calendar."
```

### Book Hotel
```
User:  "Hotels in Austin next week"
Bot:   "Found 4 options near the venue. Top choice: Hilton Downtown 
        (3.5★, $120/night, 0.2mi from venue). Type YES to book."
User:  "YES"
Bot:   "✓ Booked! Confirmation sent to your email."
```

### Book Flight
```
User:  "Flight from NYC to Miami Sept 1-5"
Bot:   "Best option: American 123 departs 8am arrives 11am ($289). 
        Return: 6pm departs arrives 9pm ($279). Type YES to book."
User:  "YES"
Bot:   "✓ Booked! Itinerary sent to your email."
```

## Development vs Production

### Development
- Uses `twilio_integration.py`
- In-memory session storage
- Great for testing and iteration
- Run with: `python twilio_integration.py`

### Production
- Uses `twilio_integration_v2.py`
- Persistent session storage (Redis/Firestore)
- Automatic session cleanup
- Multiple workers for concurrency
- Run with: `gunicorn -w 4 --worker-class eventlet -b 0.0.0.0:5000 twilio_integration_v2:app`

## Deployment Options

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions:

1. **AWS Lambda + API Gateway** - Serverless, pay-per-request
2. **Google Cloud Run** - Container-based, simple scaling
3. **Heroku** - Platform-as-a-Service, easy setup
4. **DigitalOcean App Platform** - Docker-native deployment
5. **Traditional VPS** - Full control, any cloud provider

## Configuration

### Environment Variables

```bash
# Required
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+1234567890

# Optional: Session backend (auto-detected if not set)
SESSION_BACKEND=redis    # or: memory, firestore

# Optional: Redis connection
REDIS_URL=redis://localhost:6379/0

# Optional: Google Cloud Project
GOOGLE_CLOUD_PROJECT=your-project-id
```

See `.env.example` for all options.

## Troubleshooting

### "Unauthorized - Invalid Twilio request signature"
- Verify TWILIO_AUTH_TOKEN is correct
- Make sure webhook URL in Twilio console matches exactly
- Check that X-Twilio-Signature header is present

### "Messages not being received"
- Verify ngrok is still running
- Check that Twilio webhook URL hasn't changed
- Look in ngrok web dashboard (http://localhost:4040) for webhook attempts

### "Sessions not persisting"
- Check that Redis/Firestore is running
- Verify connection string is correct
- Check logs for connection errors

## Next Steps

1. ✅ **Test locally** - Use ngrok for local testing
2. 🚀 **Deploy to production** - Choose a platform from DEPLOYMENT.md
3. 🔌 **Connect real data sources** - Wire up tournament/hotel/flight APIs
4. 📊 **Add monitoring** - Set up logging and alerting
5. 🎨 **Customize responses** - Adjust SMS formatting for your use case

## Need Help?

- **Twilio Setup**: https://www.twilio.com/docs/sms/quickstart
- **Orchestrator**: See comments in orchestrator.py
- **Session Manager**: See comments in session_manager.py
- **Deployment**: See DEPLOYMENT.md

## API Reference

### SMS Webhook Handler
- **Endpoint**: `POST /sms`
- **Validation**: X-Twilio-Signature header
- **Response**: Sends SMS via Twilio

### Health Check
- **Endpoint**: `GET /health`
- **Response**: `{"status": "healthy", "backend": "redis"}`

### Session Cleanup
- **Endpoint**: `POST /sessions/cleanup`
- **Response**: `{"status": "success", "sessions_cleaned": 5}`
- **Use case**: Call from cron job to clean expired sessions

## Architecture Diagram

```
SMS Incoming (Twilio)
        ↓
    /sms webhook
        ↓
    Validate request
        ↓
    Get/Create session
        ↓
    Send to orchestrator
        ↓
  ┌─────┴─────┐
  ↓           ↓
Route to:   Handle:
├─ tournament├─ confirmation ("YES/NO")
├─ hotel     ├─ side effects (email/calendar)
└─ flight    └─ session state
        ↓
    Format response
        ↓
   Send SMS (Twilio)
        ↓
  SMS to User
```

## Performance Metrics

- **Typical response time**: 2-5 seconds (includes LLM inference)
- **SMS delivery**: 1-3 seconds after orchestrator response
- **Concurrent users**: Scales with worker count
- **Session storage**: ~1KB per user (in-memory)

## Cost Estimation

- **Twilio SMS**: $0.0075 per incoming SMS, $0.0075 per outgoing SMS
- **Google ADK**: Included with Google Cloud Platform
- **Hosting**: Depends on platform (see DEPLOYMENT.md)
- **Storage**: Minimal (sessions only, not stored long-term)

Example: 1000 SMS/month = ~$15/month on Twilio + hosting costs
