# ORCA — Athlete Logistics Assistant

ORCA helps competitive athletes (and their parents) plan tournament travel
end to end: find a tournament that fits the player's ranking and recent
form, then recommend a flight and a hotel that actually get them there on
time and within budget. A dashboard shows the season's schedule alongside
booked flights/hotels, and a chat surface handles the "type YES to confirm"
booking flow.

<img width="1449" height="767" alt="image" src="https://github.com/user-attachments/assets/5831dcba-3720-4155-9cce-e04065e1958b" />

<img width="1141" height="680" alt="image" src="https://github.com/user-attachments/assets/ba2f6290-1221-4e64-a9aa-dce434aa6590" />

<img width="1099" height="737" alt="image" src="https://github.com/user-attachments/assets/b94fa2fd-0221-453a-be93-661b9530e60b" />

<img width="405" height="724" alt="image" src="https://github.com/user-attachments/assets/19b55661-be95-48f8-a1f3-1a693a9b29ac" />



## How it's built

- **Orchestrator agent** ([orchestrator.py](orchestrator.py)) — a Google ADK
  agent that routes intent to the sub-agents below, owns the confirm/cancel
  state machine for bookings, and triggers side effects (registration
  record, calendar event, email receipt) once a booking is confirmed.
- **Sub-agents** ([sub-agents/](sub-agents/)) — each returns structured
  recommendations only; none of them book, charge, or confirm anything:
  - [tournament.py](sub-agents/tournament.py) — ranks candidate tournaments
    against a player's ranking/recent match history.
  - [flights.py](sub-agents/flights.py) — outbound/return flight options
    that respect the event schedule and budget.
  - [hotels.py](sub-agents/hotels.py) — hotel options near the venue for
    the trip's date range.
  - [search.py](sub-agents/search.py) — dashboard-only tournament discovery
    via Gemini's Google Search grounding (separate from the SMS/orchestrator
    flow — see its docstring for why).
- **Flask API** ([server.py](server.py)) — bridges the frontend to the
  orchestrator/search agents and to local persistence.
- **Data layer** ([data_store.py](data_store.py)) — local JSON file
  ([data/local_store.json](data/local_store.json)) standing in for
  Firestore, so the app runs end to end without GCP credentials for data
  storage. Swap in real Firestore calls later without changing the schemas.
- **Frontend** ([frontend/](frontend/)) — a Vite + React dashboard (calendar,
  ORCA Search panel, journal) that talks to the Flask API.

Flight and hotel search tools are currently stubbed with mock data (see the
`TODO`s in [flights.py](sub-agents/flights.py) /
[hotels.py](sub-agents/hotels.py)); `.env` is already set up with Duffel and
RapidAPI/Booking.com credentials for wiring in real search next. The
tournament model runs against Gemini via Vertex AI.

## Prerequisites

- Python 3.11+ (developed against 3.14)
- Node 18+ and npm
- Access to a GCP project with Vertex AI enabled, authenticated via
  [Application Default Credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc)
  (`gcloud auth application-default login`) — this app uses Vertex AI, not
  an AI Studio API key
- A [Duffel](https://duffel.com) test API token (flights)
- A [RapidAPI](https://rapidapi.com) key subscribed to the Booking.com API
  (hotels)

## Setup

```bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

Copy `.env` (create it if it doesn't exist) and fill in:

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GOOGLE_CLOUD_LOCATION=global

DUFFEL_API_TOKEN=duffel_test_...
RAPIDAPI_KEY=...
RAPIDAPI_HOST=booking-com15.p.rapidapi.com
```

`.env` is gitignored — never commit real keys. Session storage
(`SESSION_BACKEND`, `REDIS_URL`) is optional and defaults to in-memory; see
the comments in `.env` for the Redis/Firestore options.

## Running it

Start the API (from the repo root):

```bash
source .venv/bin/activate
python3 server.py
```

This serves the Flask API on `http://localhost:8080`.

In a separate terminal, start the frontend dev server:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` — Vite proxies `/api` requests to the Flask
server on port 8080.

## Project layout

```
orchestrator.py         top-level ADK agent + confirmation state machine
server.py                Flask API for the dashboard
data_store.py            local JSON persistence (stand-in for Firestore)
sub-agents/
  tournament.py           tournament recommendation agent
  flights.py               flight recommendation agent
  hotels.py                 hotel recommendation agent
  search.py                  dashboard tournament discovery (Search grounding)
frontend/                React + Vite dashboard
data/local_store.json    local dev data (gitignored)
```
