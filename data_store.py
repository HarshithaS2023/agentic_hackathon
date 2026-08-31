"""
data_store.py — Local JSON-backed persistence for the dashboard API.

Stands in for the Firestore collections the ADK agents already
reference (`tournaments`, `registrations`, `search_history`) and the
journal entries the dashboard needs, so the app runs end-to-end without
GCP credentials configured. Swap a function's body for a real
`firestore.Client()` read/write once credentials are available — the
shapes returned here already match the collection schemas described in
orchestrator.py's module docstring.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from pathlib import Path
from typing import Callable

_PATH = Path(__file__).parent / "data" / "local_store.json"
_LOCK = threading.Lock()

_DEFAULT = {
    "tournaments": [],
    "flights": [],
    "hotels": [],
    "journal": [],
    "bookings": [],
    "search_history": [],
    "trips": [],
}


def _load() -> dict:
    if not _PATH.exists():
        return {k: list(v) for k, v in _DEFAULT.items()}
    with _PATH.open() as f:
        data = json.load(f)
    for k, v in _DEFAULT.items():
        data.setdefault(k, list(v))
    return data


def _save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with _PATH.open("w") as f:
        json.dump(data, f, indent=2)


def _mutate(fn: Callable[[dict], None]) -> None:
    with _LOCK:
        data = _load()
        fn(data)
        _save(data)


def list_tournaments() -> list[dict]:
    return _load()["tournaments"]


def clear_tournaments() -> None:
    """Wipe stored tournaments. Called on server startup so stale search
    results from a previous run don't linger — tournament data is a search
    cache, re-populated on demand, unlike journal entries/bookings."""

    def op(data: dict) -> None:
        data["tournaments"] = []

    _mutate(op)


def _upsert(collection: str, items: list[dict]) -> None:
    """Upsert by `id` so re-running a search doesn't duplicate rows."""

    def op(data: dict) -> None:
        rows = data[collection]
        by_id = {r.get("id"): i for i, r in enumerate(rows)}
        for item in items:
            iid = item.get("id")
            if iid in by_id:
                rows[by_id[iid]] = item
            else:
                rows.append(item)
                by_id[iid] = len(rows) - 1

    _mutate(op)


def add_tournaments(new_tournaments: list[dict]) -> None:
    _upsert("tournaments", new_tournaments)


def list_flights() -> list[dict]:
    return _load()["flights"]


def add_flights(new_flights: list[dict]) -> None:
    _upsert("flights", new_flights)


def list_hotels() -> list[dict]:
    return _load()["hotels"]


def add_hotels(new_hotels: list[dict]) -> None:
    _upsert("hotels", new_hotels)


def get_trip(trip_id: str) -> dict | None:
    return next((t for t in _load()["trips"] if t.get("trip_id") == trip_id), None)


def save_trip(fields: dict) -> dict:
    """Store a trip built from a chosen tournament — flights.py/hotels.py's
    get_trip_requirements()/get_trip_lodging_requirements() read it back by
    trip_id to derive dates, destination, and budget for their agents."""
    trip = dict(fields)
    trip.setdefault("trip_id", uuid.uuid4().hex)
    _mutate(lambda data: data["trips"].append(trip))
    return trip


def list_journal(user_id: str) -> list[dict]:
    entries = [e for e in _load()["journal"] if e.get("user_id") == user_id]
    return sorted(entries, key=lambda e: e.get("date", ""), reverse=True)


def add_journal_entry(fields: dict) -> dict:
    entry = dict(fields)
    entry.setdefault("id", uuid.uuid4().hex)
    entry.setdefault("date", dt.date.today().isoformat())
    _mutate(lambda data: data["journal"].append(entry))
    return entry


def list_bookings(user_id: str | None = None) -> list[dict]:
    bookings = _load()["bookings"]
    if user_id:
        return [b for b in bookings if b.get("user_id") == user_id]
    return bookings


def add_booking(fields: dict) -> dict:
    booking = dict(fields)
    booking.setdefault("id", uuid.uuid4().hex)
    _mutate(lambda data: data["bookings"].append(booking))
    return booking


def add_search_history(entry: dict) -> None:
    _mutate(lambda data: data["search_history"].append(entry))
