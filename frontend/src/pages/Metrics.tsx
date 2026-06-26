import { useState, useEffect } from 'react';
import { fetchMetrics } from '../api';

const GROUPS: Record<string, string[]> = {
  'Requests': ['reasoning_count', 'stream_requests', 'rate_limit_hits', 'average_latency_ms'],
  'Provider': ['provider_errors', 'provider_retries', 'fallback_count'],
  'Tools': ['tool_requests', 'tool_errors'],
  'Browser': ['browser_requests', 'browser_errors'],
  'Execution': ['active_tasks', 'completed_tasks', 'failed_tasks', 'total_steps'],
};

export default function Metrics() {
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const load = () => {
      fetchMetrics().then((data) => {
        if (active) { setMetrics(data); setError(''); }
      }).catch((e) => { if (active) setError(String(e)); }).finally(() => { if (active) setLoading(false); });
    };
    load();
    const id = setInterval(load, 5000);
    return () => { active = false; clearInterval(id); };
  }, []);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Metrics</h1>
      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500 text-sm bg-red-50 dark:bg-red-900/20 p-3 rounded-lg">{error}</div>}
      {Object.entries(GROUPS).map(([group, keys]) => (
        <div key={group}>
          <h2 className="text-lg font-semibold mb-3">{group}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {keys.map((k) => (
              <div key={k} className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
                <div className="text-xs text-gray-500">{k.replace(/_/g, ' ')}</div>
                <div className="text-xl font-bold">{metrics[k] ?? '—'}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
