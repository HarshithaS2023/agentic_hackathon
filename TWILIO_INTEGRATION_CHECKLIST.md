# Twilio SMS Integration Implementation Checklist

Complete this checklist to fully integrate Twilio SMS with your orchestrator.

## Phase 1: Setup & Testing (Day 1)

### Twilio Account Setup
- [ ] Create Twilio account at https://www.twilio.com
- [ ] Verify phone number (required for SMS)
- [ ] Buy a Twilio phone number
- [ ] Enable SMS capability on the number
- [ ] Copy Account SID from dashboard
- [ ] Copy Auth Token from dashboard (store securely!)
- [ ] Create a `.env` file with credentials (DON'T commit!)
- [ ] Add `.env` to `.gitignore`

### Local Development Setup
- [ ] Install Python dependencies: `pip install -r requirements-twilio.txt`
- [ ] Test orchestrator locally: `python orchestrator.py`
- [ ] Start SMS server: `python twilio_integration.py`
- [ ] Install ngrok for local testing: https://ngrok.com/download
- [ ] Run ngrok: `ngrok http 5000`
- [ ] Copy ngrok URL (e.g., https://abc123.ngrok.io)

### Webhook Configuration
- [ ] Go to Twilio Console → Phone Numbers
- [ ] Click on your Twilio phone number
- [ ] Scroll to "Messaging" section
- [ ] Under "A MESSAGE COMES IN", select "Webhook"
- [ ] Paste ngrok URL: `https://abc123.ngrok.io/sms`
- [ ] Make sure method is "HTTP POST"
- [ ] Save changes
- [ ] Test by texting your Twilio number

### Manual Testing
- [ ] Text: "Find me a tournament"
  - [ ] Orchestrator responds with tournament recommendations
  - [ ] Response appears in terminal logs
  - [ ] No errors in ngrok logs
  
- [ ] Text: "Search hotels in Austin"
  - [ ] Orchestrator responds with hotel options
  - [ ] Response splits into multiple SMS if needed
  
- [ ] Text: "YES"
  - [ ] Orchestrator confirms the booking
  - [ ] Session state is maintained
  
- [ ] Test confirmation flow end-to-end
  - [ ] Request tournament → Gets recommendation
  - [ ] Type YES → Booking confirmed
  - [ ] Check orchestrator logs for "confirmed" state

## Phase 2: Production Setup (Day 2)

### Session Storage
Choose ONE of the following:

#### Option A: Redis (Recommended)
- [ ] Install Redis locally for testing
- [ ] Install redis Python package: `pip install redis`
- [ ] Set REDIS_URL environment variable
- [ ] Test with `twilio_integration_v2.py`
- [ ] Verify sessions persist across restarts

#### Option B: Firestore (Google Cloud)
- [ ] Create Google Cloud Project
- [ ] Enable Firestore API
- [ ] Create Firestore database
- [ ] Install google-cloud-firestore: `pip install google-cloud-firestore`
- [ ] Set GOOGLE_CLOUD_PROJECT environment variable
- [ ] Test with `twilio_integration_v2.py`
- [ ] Verify sessions persist in Firestore console

#### Option C: In-Memory (Development Only)
- [ ] Note: Sessions lost on restart!
- [ ] Only for development/testing
- [ ] Add TODO: replace with Redis/Firestore for production

### Deployment Platform
Choose ONE platform:

#### AWS Lambda + API Gateway
- [ ] Install Serverless Framework: `npm install -g serverless`
- [ ] Create `serverless.yml` (use template from DEPLOYMENT.md)
- [ ] Deploy: `serverless deploy`
- [ ] Update Twilio webhook URL to Lambda endpoint
- [ ] Test with real SMS

#### Google Cloud Run
- [ ] Create Cloud Run service
- [ ] Push Docker image or connect GitHub repo
- [ ] Set environment variables
- [ ] Update Twilio webhook to Cloud Run URL
- [ ] Test with real SMS

#### Heroku
- [ ] Create Heroku app
- [ ] Add Redis add-on
- [ ] Push code: `git push heroku main`
- [ ] Set environment variables via dashboard
- [ ] Update Twilio webhook to Heroku URL
- [ ] Test with real SMS

#### Traditional VPS (EC2, Linode, DigitalOcean)
- [ ] SSH into VPS
- [ ] Install dependencies (Python, Redis, Nginx, Supervisor)
- [ ] Clone repo
- [ ] Set up environment variables in `.env`
- [ ] Configure Supervisor for process management
- [ ] Configure Nginx as reverse proxy
- [ ] Set up SSL with Certbot
- [ ] Update Twilio webhook URL
- [ ] Test with real SMS

### Production Validation
- [ ] Update Twilio webhook URL to production domain
- [ ] Test incoming SMS from real phone number
- [ ] Verify HTTPS is working (Twilio requires secure webhooks)
- [ ] Check that X-Twilio-Signature validation passes
- [ ] Verify sessions persist across multiple restarts
- [ ] Test long-running conversations (>30 min)
- [ ] Test with concurrent users

## Phase 3: Data Integration (Day 3-4)

### Orchestrator Functions
- [ ] Replace stub `get_player_profile()` with real data source
- [ ] Replace stub `search_tournaments()` with real tournament data
- [ ] Replace stub `register_player_for_tournament()` with Firestore write
- [ ] Replace stub `_add_calendar_event()` with Google Calendar API
- [ ] Replace stub `_send_email_receipt()` with SendGrid/SMTP

### Hotels Sub-Agent
- [ ] Replace stub `get_trip_requirements()` with Firestore query
- [ ] Replace stub `search_hotels()` with real hotel API (Google Places/Amadeus)
- [ ] Implement hotel booking logic
- [ ] Test hotel search flow end-to-end

### Flights Sub-Agent
- [ ] Replace stub `get_trip_requirements()` with Firestore query
- [ ] Replace stub `search_flights()` with real flight API (Amadeus/Skyscanner)
- [ ] Implement flight booking logic
- [ ] Test flight search flow end-to-end

### Database Schema
- [ ] Create Firestore collections:
  - [ ] `players` - User profiles and preferences
  - [ ] `tournaments` - Available tournaments
  - [ ] `registrations` - Player registrations
  - [ ] `hotels` - Hotel inventory
  - [ ] `flights` - Flight options
  - [ ] `bookings` - Hotel/flight bookings
  - [ ] `sms_sessions` - SMS session state

## Phase 4: Testing & Quality Assurance (Day 5)

### Automated Tests
- [ ] Run `python twilio_test_examples.py`
- [ ] All tests pass
- [ ] Test tournament search
- [ ] Test hotel search
- [ ] Test flight search
- [ ] Test confirmation flow
- [ ] Test session persistence
- [ ] Test multiple users

### Integration Tests
- [ ] Tournament booking flow end-to-end
- [ ] Hotel booking flow end-to-end
- [ ] Flight booking flow end-to-end
- [ ] Error handling (invalid inputs)
- [ ] Session timeout handling
- [ ] Confirmation expiry (30 minutes)
- [ ] Long messages split correctly

### Performance Testing
- [ ] Response time < 10 seconds for typical request
- [ ] Handle 10 concurrent users
- [ ] Handle 100 SMS/hour
- [ ] Memory usage stable over 24 hours
- [ ] No session leaks

### Security Testing
- [ ] Twilio signature validation working
- [ ] Invalid requests rejected (403)
- [ ] Auth token not logged or exposed
- [ ] User data isolated per session
- [ ] Session data encrypted (if using external storage)

## Phase 5: Monitoring & Operations (Ongoing)

### Logging & Monitoring
- [ ] Set up centralized logging (CloudWatch/Stackdriver/ELK)
- [ ] Monitor SMS success rate
- [ ] Track response time percentiles (p50, p95, p99)
- [ ] Alert on errors (>5 per hour)
- [ ] Monitor Redis/Firestore connection health

### Error Handling
- [ ] Test network failures (Twilio API down)
- [ ] Test orchestrator timeout (LLM takes >30s)
- [ ] Test database failures (Firestore down)
- [ ] Test rate limiting (>1000 SMS/hour)
- [ ] Verify graceful degradation

### Scheduled Maintenance
- [ ] Setup session cleanup job (hourly)
- [ ] Setup reminder job (2 days before tournament)
- [ ] Monitor and trim old session data
- [ ] Archive registration data after 1 year

## Phase 6: Documentation (Ongoing)

### User Documentation
- [ ] Create SMS help/commands guide
- [ ] Document supported requests
- [ ] Provide example conversations
- [ ] Create FAQ document
- [ ] Setup feedback/support channel

### Developer Documentation
- [ ] Update README with SMS integration info
- [ ] Document API endpoints
- [ ] Document Firestore schema
- [ ] Document deployment procedures
- [ ] Create troubleshooting guide

### Operational Documentation
- [ ] Create runbook for common issues
- [ ] Document monitoring/alerting setup
- [ ] Create incident response procedure
- [ ] Document backup/restore procedures
- [ ] Document rollback procedures

## Phase 7: Optimization (After Launch)

### Cost Optimization
- [ ] Analyze Twilio SMS costs
- [ ] Identify high-volume patterns
- [ ] Optimize message length to reduce SMS count
- [ ] Consider Twilio bulk rates if volume high
- [ ] Analyze hosting costs, optimize resource allocation

### Performance Optimization
- [ ] Profile orchestrator response time
- [ ] Optimize sub-agent inference time
- [ ] Cache tournament/hotel/flight data
- [ ] Add Redis caching layer for frequent requests
- [ ] Optimize database queries

### Feature Enhancements
- [ ] Add support for MMS (images)
- [ ] Add support for video confirmations
- [ ] Implement user preferences learning
- [ ] Add support for groups/team bookings
- [ ] Add loyalty/reward integration

## File Checklist

Ensure all files are created:

- [x] `twilio_integration.py` - Basic webhook handler
- [x] `twilio_integration_v2.py` - Production webhook handler
- [x] `session_manager.py` - Session storage abstraction
- [x] `TWILIO_SETUP.md` - Detailed setup guide
- [x] `TWILIO_QUICKSTART.md` - Quick start guide
- [x] `DEPLOYMENT.md` - Production deployment guide
- [x] `twilio_test_examples.py` - Test suite
- [x] `requirements-twilio.txt` - Python dependencies
- [x] `.env.example` - Environment variables template
- [x] `setup_twilio.sh` - Automated setup script
- [x] `TWILIO_INTEGRATION_CHECKLIST.md` - This file!

## Environment Variables Checklist

Ensure these are set before running:

### Required
- [ ] `TWILIO_ACCOUNT_SID`
- [ ] `TWILIO_AUTH_TOKEN`
- [ ] `TWILIO_PHONE_NUMBER`

### Optional (for production)
- [ ] `REDIS_URL` (if using Redis for sessions)
- [ ] `GOOGLE_CLOUD_PROJECT` (if using Firestore for sessions)
- [ ] `FLASK_ENV=production`
- [ ] `LOG_LEVEL=INFO`

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| "Invalid Twilio signature" | Verify Auth Token, check webhook URL matches exactly |
| "Messages not received" | Check ngrok running, verify Twilio webhook URL |
| "Sessions not persisting" | Check Redis/Firestore running and accessible |
| "Slow responses" | Check orchestrator LLM latency, check sub-agent performance |
| "High error rate" | Check logs, verify data sources connected, check rate limits |

## Success Criteria

Consider the integration complete when:

- [ ] User can text orchestrator and get responses
- [ ] Tournament search works end-to-end
- [ ] Hotel search works end-to-end
- [ ] Flight search works end-to-end
- [ ] Confirmation flow works (YES/NO)
- [ ] Sessions persist across messages
- [ ] Production deployment verified
- [ ] All tests passing
- [ ] Monitoring and alerting setup
- [ ] Documentation complete

## Next Steps After Integration

1. **Gather User Feedback** - Use real users to test
2. **Iterate** - Improve based on feedback
3. **Scale** - Monitor and optimize for growth
4. **Expand** - Add new capabilities (more booking types, etc.)
5. **Analytics** - Track usage patterns and success rates

## Support

- 📖 See TWILIO_QUICKSTART.md for quick start
- 📘 See TWILIO_SETUP.md for detailed setup
- 🚀 See DEPLOYMENT.md for production deployment
- 🧪 Run `python twilio_test_examples.py` to test
- 💬 Check orchestrator.py for agent implementation

---

**Last Updated**: 2026-08-31
**Status**: Ready for implementation
