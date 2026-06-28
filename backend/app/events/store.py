import logging
from sqlalchemy import text
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR(12) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    session_id VARCHAR(64) DEFAULT '',
    conversation_id VARCHAR(64) DEFAULT '',
    actor VARCHAR(64) DEFAULT 'system',
    source VARCHAR(128) DEFAULT '',
    payload JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    version VARCHAR(8) DEFAULT '1.0',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

class EventStore:
    def __init__(self, session_factory=get_session):
        self.session_factory = session_factory

    async def initialize(self, session=None) -> None:
        if session is not None:
            await self._execute_schema(session)
        elif self.session_factory is not None:
            async with self.session_factory() as local_session:
                await self._execute_schema(local_session)

    async def _execute_schema(self, session) -> None:
        for stmt in CREATE_EVENTS_TABLE.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await session.execute(text(stmt))
        logger.info("Events table ready")

event_store = EventStore()
