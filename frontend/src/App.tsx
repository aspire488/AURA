import { useState, useEffect } from 'react';
import Chat from './pages/Chat';
import Memory from './pages/Memory';
import Tasks from './pages/Tasks';
import Metrics from './pages/Metrics';
import Settings from './pages/Settings';
import { fetchHealth } from './api';

type Page = 'chat' | 'memory' | 'tasks' | 'metrics' | 'settings';

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'memory', label: 'Memory', icon: '🧠' },
  { id: 'tasks', label: 'Tasks', icon: '📋' },
  { id: 'metrics', label: 'Metrics', icon: '📊' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
];

// ponytail: no react-router, just state
export default function App() {
  const [page, setPage] = useState<Page>(() => (localStorage.getItem('aura_page') as Page) || 'chat');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState<'ok' | 'degraded' | 'down'>('down');

  useEffect(() => {
    localStorage.setItem('aura_page', page);
    setSidebarOpen(false);
  }, [page]);

  useEffect(() => {
    const theme = localStorage.getItem('aura_theme') || 'dark';
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, []);

  // ponytail: health ping every 10s
  useEffect(() => {
    let active = true;
    const ping = () => {
      fetchHealth().then((h) => {
        if (active) setHealth(h.status === 'healthy' ? 'ok' : 'degraded');
      }).catch(() => { if (active) setHealth('down'); });
    };
    ping();
    const id = setInterval(ping, 10_000);
    return () => { active = false; clearInterval(id); };
  }, []);

  const healthDot = health === 'ok' ? 'bg-green-500' : health === 'degraded' ? 'bg-yellow-500' : 'bg-red-500';
  const healthLabel = health === 'ok' ? 'Healthy' : health === 'degraded' ? 'Degraded' : 'Offline';

  const pages: Record<Page, React.ReactNode> = {
    chat: <Chat />,
    memory: <Memory />,
    tasks: <Tasks />,
    metrics: <Metrics />,
    settings: <Settings />,
  };

  return (
    <div className="h-screen flex bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <button onClick={() => setSidebarOpen(!sidebarOpen)}
        className="md:hidden fixed top-3 left-3 z-50 p-2 bg-gray-200 dark:bg-gray-700 rounded-lg">☰</button>

      <aside className={`fixed md:static inset-y-0 left-0 z-40 w-56 bg-gray-100 dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col transition-transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-4 font-bold text-lg border-b dark:border-gray-700">AURA</div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV.map((n) => (
            <button key={n.id} onClick={() => setPage(n.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${page === n.id ? 'bg-blue-600 text-white' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
              <span>{n.icon}</span>{n.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t dark:border-gray-700 flex items-center gap-2 text-xs text-gray-500">
          <span className={`w-2 h-2 rounded-full ${healthDot}`} />
          {healthLabel}
        </div>
      </aside>

      {sidebarOpen && <div className="fixed inset-0 bg-black/50 z-30 md:hidden" onClick={() => setSidebarOpen(false)} />}

      <main className="flex-1 flex flex-col overflow-hidden">
        {pages[page]}
      </main>
    </div>
  );
}
