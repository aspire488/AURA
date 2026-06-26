import { useState, useEffect, useCallback } from 'react';
import { fetchMemoryStats, searchMemory } from '../api';

export default function Memory() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Array<{ chunk_id: string; text: string; score: number; role: string; timestamp: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 10;

  useEffect(() => { fetchMemoryStats().then(setStats).catch(() => {}); }, []);

  const search = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setPage(0);
    try {
      const data = await searchMemory(query);
      setResults(data.results);
    } catch (e) { setError(String(e)); setResults([]); }
    setLoading(false);
  }, [query]);

  const paged = results.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(results.length / PAGE_SIZE);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Memory</h1>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          placeholder="Search memories..."
          className="flex-1 rounded-lg border dark:border-gray-600 dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button onClick={search} disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {error && <div className="text-red-500 text-sm bg-red-50 dark:bg-red-900/20 p-3 rounded-lg">{error}</div>}

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
              <div className="text-xs text-gray-500">{k.replace(/_/g, ' ')}</div>
              <div className="text-lg font-semibold">{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      {!loading && results.length === 0 && query && !error && (
        <div className="text-gray-500 text-center py-8">No results found</div>
      )}

      {paged.length > 0 && (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Results ({results.length})</h2>
            <div className="flex gap-2 items-center text-sm">
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="px-2 py-1 rounded bg-gray-200 dark:bg-gray-700 disabled:opacity-50">Prev</button>
              <span className="text-gray-500">{page + 1} / {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="px-2 py-1 rounded bg-gray-200 dark:bg-gray-700 disabled:opacity-50">Next</button>
            </div>
          </div>
          {paged.map((r) => (
            <div key={r.chunk_id} className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>{r.role}</span>
                <span>score: {r.score.toFixed(3)}</span>
              </div>
              <div className="text-sm">{r.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
