# AURA Repository Guide

## Architecture

- **Backend** (`backend/`): FastAPI, decision layer. Do not modify.
- **Extension** (`extension/`): Chrome Manifest V3, execution layer. Communicates with backend via WebSocket.

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
