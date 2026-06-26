# AURA Repository Guide

## Architecture

- **Backend** (`backend/`): FastAPI, decision layer. Event-driven cognitive subsystem.
- **Extension** (`extension/`): Chrome Manifest V3, execution layer. Communicates via WebSocket.
- **Event System** (`backend/app/events/`): In-process pub/sub + PostgreSQL persistence. First cognitive subsystem.

## Extension Protocol

Backend WebSocket at `ws://localhost:8000/ws/browser`.

**Backend sends** to extension:
```json
{"id": "hex12", "action": "open_url", "url": "https://..."}
```

**Extension must respond** with matching `id`:
```json
{"id": "hex12", "success": true, "message": "Opened"}
```

Supported actions: `open_url`, `open_tab`, `close_tab`, `activate_tab`, `search_google`.

See `backend/app/runtime/browser_client.py` for the full protocol.

## Event System

Every significant action emits a `BaseEvent` via `emit()` from `app.main`.

**Publishing events:**
```python
from app.main import emit
await emit("user_message_received", session_id=sid, source="api/reason", payload={"query": query})
```

**Event types** (`app/events/event.py`): `USER_MESSAGE_RECEIVED`, `ASSISTANT_RESPONSE_GENERATED`, `TOOL_EXECUTION_STARTED`, `TOOL_EXECUTION_COMPLETED`, `TASK_CREATED`, `TASK_COMPLETED`, `MEMORY_STORED`, `MEMORY_RETRIEVED`, `BROWSER_ACTION`, `CODE_EXECUTED`, `PROVIDER_INVOKED`, `PROVIDER_FAILED`, `REASONING_STARTED`, `REASONING_COMPLETED`, `REFLECTION_CREATED`.

**Adding a new subscriber** (`app/events/__init__.py`):
1. Create handler class implementing `async def __call__(self, event: BaseEvent) -> None`
2. Register in `init_events()` with `registry.register(EventType.X, Handler())`
3. Wire into bus: `bus.subscribe(EventType.X, handler)`

**Event store**: PostgreSQL `events` table, auto-created on startup. Query via `event_store.list_by_session()`, `event_store.latest()`, etc.

**Metrics**: Event counts tracked in existing `RetrievalMetrics` singleton (`events_published`, `events_processed`, `subscriber_failures`).

## Extension Structure

```
extension/
├── manifest.json        # MV3, permissions: tabs, activeTab, storage
├── background.js        # Service worker: single WebSocket, command dispatch
├── content.js           # Idle placeholder (not injected by default)
├── popup/
│   ├── popup.html       # Status display
│   └── popup.js         # Reads from chrome.storage
└── icons/               # Placeholder PNGs
```

## Loading Extension

1. Go to `chrome://extensions`
2. Enable Developer mode
3. Click "Load unpacked" → select `extension/` folder
4. Backend must be running on port 8000

## Commands

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Extension: no build step, plain JS. Reload in chrome://extensions after changes.
```

## Gotchas

- `background.js` generates unique IDs via `crypto.randomUUID().slice(0, 12)` — must match backend's `uuid.uuid4().hex[:12]` format
- Popup reads status from `chrome.storage.local`, not directly from background
- Extension auto-reconnects after 2s on disconnect
- Heartbeat every 30s keeps connection alive
- Event bus starts during FastAPI lifespan; `emit()` is a no-op if called before startup
- `emit()` returns the `BaseEvent` for chaining; always pass `source=` for traceability
- Events persist to PostgreSQL; if DB is down, events log errors but don't block the caller
