import { useState, useEffect, useRef } from 'react';
import { fetchTasks, resumeTask } from '../api';

interface Task {
  task_id: string; query: string; status: string;
  steps: string[]; results: string[]; current_step: number;
  execution_trace: unknown[]; created_at: number; updated_at: number;
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-green-500 bg-green-50 dark:bg-green-900/20',
  failed: 'text-red-500 bg-red-50 dark:bg-red-900/20',
  running: 'text-blue-500 bg-blue-50 dark:bg-blue-900/20',
  pending: 'text-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
  deferred: 'text-gray-500 bg-gray-50 dark:bg-gray-800',
  cancelled: 'text-gray-400 bg-gray-50 dark:bg-gray-800',
};

function formatDuration(start: number, end: number) {
  const ms = (end - start) * 1000;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const load = () => {
    fetchTasks('').then((data) => {
      setTasks(data);
      setError('');
    }).catch((e) => setError(String(e))).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // ponytail: auto-refresh every 2s if any task is active
  useEffect(() => {
    const hasActive = tasks.some((t) => t.status === 'running' || t.status === 'pending');
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (hasActive) intervalRef.current = setInterval(load, 2000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [tasks]);

  const resume = async (id: string) => {
    await resumeTask(id);
    load();
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Tasks</h1>
      {error && <div className="text-red-500 text-sm bg-red-50 dark:bg-red-900/20 p-3 rounded-lg">{error}</div>}
      {loading && <div className="text-gray-500">Loading...</div>}
      {!loading && tasks.length === 0 && <div className="text-gray-500">No tasks yet</div>}
      {tasks.map((t) => (
        <div key={t.task_id} className="border dark:border-gray-700 rounded-lg p-4 space-y-2">
          <div className="flex justify-between items-center">
            <span className="font-mono text-xs text-gray-500">{t.task_id.slice(0, 8)}</span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400">{formatDuration(t.created_at, t.updated_at)}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[t.status] || 'text-gray-500'}`}>{t.status}</span>
            </div>
          </div>
          <div className="text-sm">{t.query}</div>
          <div className="text-xs text-gray-500">Step {t.current_step + 1} / {t.steps.length}</div>
          {t.steps.length > 0 && (
            <div className="space-y-1">
              {t.steps.map((s, i) => (
                <div key={i} className={`text-xs px-2 py-1 rounded ${
                  i < t.current_step ? 'bg-green-100 dark:bg-green-900/30' :
                  i === t.current_step ? 'bg-blue-100 dark:bg-blue-900/30' :
                  'bg-gray-100 dark:bg-gray-800'
                }`}>
                  {i < t.current_step ? '✓' : i === t.current_step ? '►' : '○'} {s}
                </div>
              ))}
            </div>
          )}
          {t.execution_trace.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-gray-500">Execution trace ({t.execution_trace.length} entries)</summary>
              <pre className="mt-1 bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(t.execution_trace, null, 2)}
              </pre>
            </details>
          )}
          {(t.status === 'pending' || t.status === 'deferred') && (
            <button onClick={() => resume(t.task_id)} className="px-3 py-1 bg-blue-600 text-white rounded text-xs">Resume</button>
          )}
        </div>
      ))}
    </div>
  );
}
