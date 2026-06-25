// popup.js – display connection status and last activity
const statusEl = document.getElementById('status');
const urlEl = document.getElementById('url');
const cmdEl = document.getElementById('cmd');
const respEl = document.getElementById('resp');
const reconnectBtn = document.getElementById('reconnect');

function update() {
  chrome.storage.local.get(['connected', 'url', 'lastCommand', 'lastResponse'], (data) => {
    statusEl.textContent = data.connected ? 'Connected' : 'Disconnected';
    statusEl.style.color = data.connected ? 'green' : 'red';
    urlEl.textContent = data.url || '—';
    cmdEl.textContent = data.lastCommand ? JSON.stringify(data.lastCommand, null, 2) : '—';
    respEl.textContent = data.lastResponse ? JSON.stringify(data.lastResponse.data, null, 2) : '—';
  });
}

reconnectBtn.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'reconnect' }, () => {
    setTimeout(update, 500);
  });
});

update();
setInterval(update, 1000);
