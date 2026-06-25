// background.js – service worker for AURA extension
// ponytail: std WebSocket, no libs, single connection
let ws = null;
let heartbeatTimer = null;
let reconnectTimer = null;
let lastCommand = null;
let lastResponse = null;
const WS_URL = 'ws://localhost:8000/ws/browser';
const HEARTBEAT_INTERVAL = 30000;

const pending = new Map();

function log(...args) { console.log('[AURA bg]', ...args); }

function setStatus(connected) {
  chrome.storage.local.set({ connected, url: WS_URL });
  chrome.runtime.sendMessage({ type: 'status', connected, url: WS_URL }).catch(() => {});
}

function startHeartbeat() {
  clearInterval(heartbeatTimer);
  heartbeatTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, HEARTBEAT_INTERVAL);
}

function connect() {
  if (ws) return;
  log('Connecting to', WS_URL);
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    log('Connected');
    setStatus(true);
    startHeartbeat();
  };
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      const msgId = msg.id;
      if (msgId && pending.has(msgId)) {
        const { port, action } = pending.get(msgId);
        lastResponse = { action, data: msg, time: Date.now() };
        chrome.storage.local.set({ lastResponse });
        port.postMessage({ type: 'response', id: msgId, data: msg });
        pending.delete(msgId);
      }
    } catch (err) { log('Parse error', err); }
  };
  ws.onclose = () => {
    log('Disconnected');
    setStatus(false);
    ws = null;
    clearInterval(heartbeatTimer);
    reconnectTimer = setTimeout(connect, 2000);
  };
  ws.onerror = (e) => {
    log('Error', e);
    ws?.close();
  };
}

connect();

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'command' && ws && ws.readyState === WebSocket.OPEN) {
    const id = crypto.randomUUID().slice(0, 12);
    const payload = { id, action: msg.action };
    if (msg.params) Object.assign(payload, msg.params);
    lastCommand = { action: msg.action, params: msg.params, time: Date.now() };
    chrome.storage.local.set({ lastCommand });
    pending.set(id, { port: sender, action: msg.action });
    ws.send(JSON.stringify(payload));
    return true;
  }
  if (msg.type === 'reconnect') {
    if (ws) ws.close();
    connect();
    sendResponse({ ok: true });
    return false;
  }
});
