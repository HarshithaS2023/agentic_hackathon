"""
session_manager.py — Session management for Twilio SMS integration

Provides abstraction layer for storing and retrieving user sessions.
Supports in-memory (dev), Redis (production), and Firestore (scalable).

Usage:
    manager = SessionManager.create()  # Auto-detects backend
    session = manager.get_or_create(phone_number)
    session.set("key", value)
    session.save()
"""

from __future__ import annotations

import abc
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from google.adk.runners import InMemoryRunner
from orchestrator import orchestrator


# Session TTL (how long before a session is auto-cleared)
SESSION_TTL_HOURS = 24


class UserSession:
    """Represents a user's conversation session."""

    def __init__(
        self,
        phone_number: str,
        runner: InMemoryRunner,
        session_id: str,
    ):
        self.phone_number = phone_number
        self.runner = runner
        self.session_id = session_id
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """Store a value in the session."""
        self.data[key] = value
        self.last_activity = datetime.now(timezone.utc)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the session."""
        self.last_activity = datetime.now(timezone.utc)
        return self.data.get(key, default)

    def is_expired(self) -> bool:
        """Check if the session has expired."""
        expires_at = self.last_activity + timedelta(hours=SESSION_TTL_HOURS)
        return datetime.now(timezone.utc) > expires_at

    def to_dict(self) -> dict:
        """Serialize session to dict for storage."""
        return {
            "phone_number": self.phone_number,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict, runner: InMemoryRunner) -> UserSession:
        """Deserialize session from dict."""
        session = cls(
            phone_number=data["phone_number"],
            runner=runner,
            session_id=data["session_id"],
        )
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_activity = datetime.fromisoformat(data["last_activity"])
        session.data = data.get("data", {})
        return session


class SessionBackend(abc.ABC):
    """Abstract base class for session storage backends."""

    @abc.abstractmethod
    async def get(self, phone_number: str) -> Optional[dict]:
        """Retrieve a session by phone number."""
        pass

    @abc.abstractmethod
    async def save(self, phone_number: str, session_data: dict) -> None:
        """Save a session."""
        pass

    @abc.abstractmethod
    async def delete(self, phone_number: str) -> None:
        """Delete a session."""
        pass

    @abc.abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        pass


class InMemorySessionBackend(SessionBackend):
    """Simple in-memory session storage (development only)."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}

    async def get(self, phone_number: str) -> Optional[dict]:
        return self.sessions.get(phone_number)

    async def save(self, phone_number: str, session_data: dict) -> None:
        self.sessions[phone_number] = session_data

    async def delete(self, phone_number: str) -> None:
        self.sessions.pop(phone_number, None)

    async def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        expired_keys = [
            key
            for key, data in self.sessions.items()
            if datetime.fromisoformat(data["last_activity"])
            + timedelta(hours=SESSION_TTL_HOURS)
            < datetime.now(timezone.utc)
        ]
        for key in expired_keys:
            del self.sessions[key]
        return len(expired_keys)


class RedisSessionBackend(SessionBackend):
    """Redis-based session storage (production)."""

    def __init__(self, redis_url: Optional[str] = None):
        try:
            import redis.asyncio as redis

            self.redis_url = redis_url or os.getenv(
                "REDIS_URL", "redis://localhost:6379/0"
            )
            self.client = None  # Lazy init
        except ImportError:
            raise ImportError(
                "redis is required for RedisSessionBackend. "
                "Install with: pip install redis"
            )

    async def _ensure_connected(self):
        if self.client is None:
            import redis.asyncio as redis

            self.client = redis.from_url(self.redis_url)

    async def get(self, phone_number: str) -> Optional[dict]:
        await self._ensure_connected()
        data = await self.client.get(f"session:{phone_number}")
        return json.loads(data) if data else None

    async def save(self, phone_number: str, session_data: dict) -> None:
        await self._ensure_connected()
        await self.client.setex(
            f"session:{phone_number}",
            SESSION_TTL_HOURS * 3600,
            json.dumps(session_data),
        )

    async def delete(self, phone_number: str) -> None:
        await self._ensure_connected()
        await self.client.delete(f"session:{phone_number}")

    async def cleanup_expired(self) -> int:
        """Redis handles expiry automatically, so this is a no-op."""
        return 0


class FirestoreSessionBackend(SessionBackend):
    """Firestore-based session storage (scalable, integrated with orchestrator data)."""

    def __init__(self, project_id: Optional[str] = None):
        try:
            from google.cloud import firestore

            self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
            self.db = firestore.AsyncClient(project=self.project_id)
            self.collection = "sms_sessions"
        except ImportError:
            raise ImportError(
                "google-cloud-firestore is required for FirestoreSessionBackend. "
                "Install with: pip install google-cloud-firestore"
            )

    async def get(self, phone_number: str) -> Optional[dict]:
        doc = await self.db.collection(self.collection).document(
            phone_number
        ).get()
        return doc.to_dict() if doc.exists else None

    async def save(self, phone_number: str, session_data: dict) -> None:
        await self.db.collection(self.collection).document(phone_number).set(
            session_data
        )

    async def delete(self, phone_number: str) -> None:
        await self.db.collection(self.collection).document(phone_number).delete()

    async def cleanup_expired(self) -> int:
        """Remove sessions where last_activity is older than TTL."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_TTL_HOURS)
        docs = await (
            self.db.collection(self.collection)
            .where("last_activity", "<", cutoff.isoformat())
            .stream()
        )
        count = 0
        async for doc in docs:
            await doc.reference.delete()
            count += 1
        return count


class SessionManager:
    """Manages user sessions with pluggable backend storage."""

    def __init__(self, backend: SessionBackend):
        self.backend = backend
        self.runners: dict[str, InMemoryRunner] = {}

    @staticmethod
    def create(backend: Optional[str] = None) -> SessionManager:
        """Factory method to create a SessionManager with the appropriate backend.
        
        Args:
            backend: "memory" (dev), "redis" (production), "firestore" (scalable).
                     If None, auto-detects based on environment.
        
        Returns:
            A SessionManager instance.
        """
        if backend is None:
            # Auto-detect
            if os.getenv("REDIS_URL"):
                backend = "redis"
            elif os.getenv("GOOGLE_CLOUD_PROJECT"):
                backend = "firestore"
            else:
                backend = "memory"

        if backend == "memory":
            return SessionManager(InMemorySessionBackend())
        elif backend == "redis":
            return SessionManager(RedisSessionBackend())
        elif backend == "firestore":
            return SessionManager(FirestoreSessionBackend())
        else:
            raise ValueError(f"Unknown backend: {backend}")

    async def get_or_create(self, phone_number: str) -> UserSession:
        """Get an existing session or create a new one.
        
        Args:
            phone_number: User's phone number.
            
        Returns:
            A UserSession instance.
        """
        # Check for existing session in backend
        session_data = await self.backend.get(phone_number)

        if session_data:
            # Restore existing session
            if phone_number not in self.runners:
                # Re-create the runner (runners aren't persisted)
                runner = InMemoryRunner(agent=orchestrator, app_name="orchestrator_sms")
                self.runners[phone_number] = runner
            else:
                runner = self.runners[phone_number]

            session = UserSession.from_dict(session_data, runner)
            return session

        # Create new session
        runner = InMemoryRunner(agent=orchestrator, app_name="orchestrator_sms")
        session_obj = await runner.session_service.create_session(
            app_name="orchestrator_sms",
            user_id=phone_number,
        )

        self.runners[phone_number] = runner

        session = UserSession(
            phone_number=phone_number,
            runner=runner,
            session_id=session_obj.session_id,
        )

        # Save to backend
        await self.backend.save(phone_number, session.to_dict())

        return session

    async def save_session(self, session: UserSession) -> None:
        """Persist a session to the backend.
        
        Args:
            session: The UserSession to save.
        """
        await self.backend.save(session.phone_number, session.to_dict())

    async def delete_session(self, phone_number: str) -> None:
        """Delete a session.
        
        Args:
            phone_number: User's phone number.
        """
        await self.backend.delete(phone_number)
        self.runners.pop(phone_number, None)

    async def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.
        
        Returns:
            Number of sessions removed.
        """
        return await self.backend.cleanup_expired()
