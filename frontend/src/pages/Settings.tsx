import { useState, useEffect } from 'react';

function getSetting(key: string, fallback: string) {
  return localStorage.getItem(`aura_${key}`) || fallback;
}

export default function Settings() {
  const [backendUrl, setBackendUrl] = useState(() => getSetting('backend_url', 'http://localhost:8000'));
  const [provider, setProvider] = useState(() => getSetting('provider', 'openai'));
  const [theme, setTheme] = useState(() => getSetting('theme', 'dark'));
  const [autoScroll, setAutoScroll] = useState(() => getSetting('auto_scroll', 'true') === 'true');
  const [streaming, setStreaming] = useState(() => getSetting('streaming', 'true') === 'true');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const save = () => {
    localStorage.setItem('aura_backend_url', backendUrl);
    localStorage.setItem('aura_provider', provider);
    localStorage.setItem('aura_theme', theme);
    localStorage.setItem('aura_auto_scroll', String(autoScroll));
    localStorage.setItem('aura_streaming', String(streaming));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const toggle = (v: boolean, setter: (v: boolean) => void) => () => setter(!v);

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Backend URL</span>
        <input value={backendUrl} onChange={(e) => setBackendUrl(e.target.value)}
          className="w-full rounded-lg border dark:border-gray-600 dark:bg-gray-800 px-3 py-2 text-sm" />
      </label>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Provider</span>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}
          className="w-full rounded-lg border dark:border-gray-600 dark:bg-gray-800 px-3 py-2 text-sm">
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="google">Google</option>
        </select>
      </label>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Theme</span>
        <select value={theme} onChange={(e) => setTheme(e.target.value)}
          className="w-full rounded-lg border dark:border-gray-600 dark:bg-gray-800 px-3 py-2 text-sm">
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>

      <div className="space-y-3">
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={autoScroll} onChange={toggle(autoScroll, setAutoScroll)} className="w-4 h-4" />
          <span className="text-sm">Auto-scroll chat</span>
        </label>
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={streaming} onChange={toggle(streaming, setStreaming)} className="w-4 h-4" />
          <span className="text-sm">Enable streaming responses</span>
        </label>
      </div>

      <button onClick={save} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">
        {saved ? 'Saved!' : 'Save'}
      </button>
    </div>
  );
}
