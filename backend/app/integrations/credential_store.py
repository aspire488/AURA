"""Persistent encrypted credential store for integrations.

Uses SQLAlchemy (async) with PostgreSQL (or SQLite for dev).
Encryption with Fernet – key from AURA_ENCRYPTION_KEY env var.
"""

import datetime
import uuid
from typing import List, Optional, Dict, Any

from cryptography.fernet import Fernet

from sqlalchemy import Column, String, DateTime, Boolean, JSON, LargeBinary, Index
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------
engine = create_async_engine(settings.postgres_url, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class Credential(Base):
    __tablename__ = "integration_credentials"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String, nullable=False, index=True)
    access_token = Column(LargeBinary, nullable=False)
    refresh_token = Column(LargeBinary, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(JSON, nullable=True)
    meta = Column("metadata", JSON, nullable=True)
    last_refresh = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    revoked = Column(Boolean, default=False)

    __table_args__ = (Index("ix_provider_unique", "provider", unique=True),)


class CredentialStore:
    """High‑level async API for encrypted credential persistence."""

    def __init__(self) -> None:
        key = settings.encryption_key
        if not key:
            # ponytail: generate temporary key if none provided – suitable for dev/test environments
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            # Note: this key is not persisted; restart will lose stored credentials

        # Fernet expects 32‑url‑safe base64 bytes
        self.fernet = Fernet(key.encode())

    async def init(self) -> None:
        """Create tables if they do not exist."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ---------------------------------------------------------------------
    # CRUD helpers
    # ---------------------------------------------------------------------
    async def _get_record(self, session: AsyncSession, provider: str) -> Optional[Credential]:
        result = await session.execute(
            Credential.__table__.select().where(Credential.provider == provider)
        )
        row = result.fetchone()
        return row[0] if row else None

    async def set(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime.datetime] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            enc_at = self.fernet.encrypt(access_token.encode())
            enc_rt = self.fernet.encrypt(refresh_token.encode()) if refresh_token else None
            record = await self._get_record(session, provider)
            now = datetime.datetime.utcnow()
            if record:
                record.access_token = enc_at
                record.refresh_token = enc_rt
                record.expires_at = expires_at
                record.scopes = scopes
                record.meta = metadata
                record.last_refresh = now
                record.last_error = None
                record.revoked = False
            else:
                record = Credential(
                    provider=provider,
                    access_token=enc_at,
                    refresh_token=enc_rt,
                    expires_at=expires_at,
                    scopes=scopes,
                    metadata=metadata,
                    last_refresh=now,
                )
                session.add(record)
            await session.commit()

    async def get(self, provider: str) -> Optional[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            record = await self._get_record(session, provider)
            if not record:
                return None
            return {
                "access_token": self.fernet.decrypt(record.access_token).decode(),
                "refresh_token": self.fernet.decrypt(record.refresh_token).decode() if record.refresh_token else None,
                "expires_at": record.expires_at,
                "scopes": record.scopes,
                "metadata": record.meta,
                "last_refresh": record.last_refresh,
                "last_error": record.last_error,
                "revoked": record.revoked,
            }

    async def revoke(self, provider: str) -> None:
        async with AsyncSessionLocal() as session:
            record = await self._get_record(session, provider)
            if record:
                record.revoked = True
                await session.commit()

    async def delete(self, provider: str) -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(Credential.__table__.delete().where(Credential.provider == provider))
            await session.commit()

# singleton instance used by the application
credential_store = CredentialStore()
