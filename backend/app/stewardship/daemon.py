import asyncio
import logging
from app.stewardship.manager import detect_orphan_relationships, detect_stalled_imports, audit_subsystem_health, repair_orphan_relationships, repair_duplicate_identities, cleanup_stalled_imports
from app.stewardship.memory_consolidation import consolidate_idle_memories
from app.stewardship.reflection import execute_system_reflection

logger = logging.getLogger(__name__)

class StewardshipDaemon:
    def __init__(self, interval_seconds: float = 30.0):
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("AURA Stewardship Background Daemon initialized.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AURA Stewardship Background Daemon stopped cleanly.")

    async def _loop(self) -> None:
        # Give the core system a moment to warm up before running audits
        await asyncio.sleep(5.0)
        while self._running:
            try:
                logger.debug("Executing proactive stewardship sweep...")
                # Run the pre-existing database integrity queries
                await detect_orphan_relationships()
                await repair_orphan_relationships()
                await detect_stalled_imports()
                await cleanup_stalled_imports()
                await audit_subsystem_health()
                await repair_duplicate_identities()
                # ponytail: flush idle conversations to long‑term storage
                await consolidate_idle_memories()
                # (Add proactive drift mitigation or cleanup actions here as required)
                await execute_system_reflection()
            except Exception as e:
                logger.error(f"Error during stewardship background execution: {str(e)}")
            # Sleep interval to maintain negligible CPU/RAM footprint
            await asyncio.sleep(self.interval)

daemon = StewardshipDaemon()
