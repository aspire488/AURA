// ponytail: typed fetch wrappers, no abstraction layer

const TIMEOUT_MS = 15_000;

const getBaseUrl = () => localStorage.getItem('aura_backend_url') || 'http://localhost:8000';

// ponytail: timeout wrapper, native AbortController
async function timedFetch(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

export async function fetchHealth() {
  const res = await timedFetch(`${getBaseUrl()}/health`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<{ status: string; version: string; services: Record<string, { status: string; latency_ms: number }> }>;
}

export async function fetchReady() {
  const res = await timedFetch(`${getBaseUrl()}/ready`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<{ status: string; services: Record<string, string> }>;
}

export async function fetchMetrics() {
  const res = await timedFetch(`${getBaseUrl()}/metrics`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<Record<string, number>>;
}

export async function fetchTasks(sessionId: string) {
  const res = await timedFetch(`${getBaseUrl()}/tasks?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<Array<{
    task_id: string; session_id: string; query: string;
    status: string; steps: string[]; results: string[];
    current_step: number; execution_trace: unknown[];
    created_at: number; updated_at: number;
  }>>;
}

export async function resumeTask(taskId: string) {
  const res = await timedFetch(`${getBaseUrl()}/tasks/${taskId}/resume`, { method: 'POST' });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export async function fetchMemoryStats() {
  const res = await timedFetch(`${getBaseUrl()}/memory/stats`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<{
    total_chunks: number; total_conversations: number;
    short_term: number; long_term: number; ephemeral: number;
    average_chunk_length: number; oldest_memory: string; newest_memory: string;
  }>;
}

export async function searchMemory(query: string, topK = 10) {
  const res = await timedFetch(`${getBaseUrl()}/retrieval/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<{ results: Array<{ chunk_id: string; text: string; score: number; role: string; timestamp: string }> }>;
}

export interface StreamEvent {
  type: 'thinking' | 'result' | 'done' | 'error';
  message?: string;
  answer?: string;
  intent?: string;
  citations?: string[];
  partial?: string;
}

export function streamReason(
  query: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
) {
  const controller = signal ? undefined : new AbortController();
  fetch(`${getBaseUrl()}/reason`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId, stream: true }),
    signal: signal || controller?.signal,
  }).then(async (res) => {
    if (!res.ok) throw new Error(`${res.status}`);
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop()!;
      for (const part of parts) {
        const line = part.trim();
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch { /* skip malformed */ }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onEvent({ type: 'error', message: String(err) });
    }
  });
  return controller;
}
