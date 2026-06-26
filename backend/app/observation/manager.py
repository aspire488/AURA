from .store import observation_store

class ObservationManager:
    """Thin wrapper delegating to ObservationStore.
    ponytail: no extra logic needed; provides manager interface for consistency.
    """
    async def initialize(self) -> None:
        await observation_store.initialize()
