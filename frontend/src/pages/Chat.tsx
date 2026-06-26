import { useState, useRef, useEffect, useCallback } from 'react';
import Markdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import { streamReason, type StreamEvent } from '../api';

interface Message { role: 'user' | 'assistant'; content: string; thinking?: string; }

// ponytail: localStorage session persistence
function loadMessages(): Message[] {
  try { return JSON.parse(localStorage.getItem('aura_chat_messages') || '[]'); } catch { return []; }
}
function saveMessages(msgs: Message[]) {
  localStorage.setItem('aura_chat_messages', JSON.stringify(msgs.slice(-50)));
}

function CodeBlock({ children, ...props }: React.HTMLAttributes<HTMLElement>) {
  const [copied, setCopied] = useState(false);
  const code = String(children).replace(/\n$/, '');
  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="relative group">
      <button onClick={copy} className="absolute top-1 right-1 px-2 py-0.5 text-xs bg-gray-600 hover:bg-gray-500 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity">
        {copied ? 'Copied' : 'Copy'}
      </button>
      <code {...props}>{children}</code>
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>(loadMessages);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState('');
  const [thinking, setThinking] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autoScrollRef = useRef(true);

  const sessionId = useRef(localStorage.getItem('aura_session_id') || crypto.randomUUID().slice(0, 12));

  useEffect(() => { localStorage.setItem('aura_session_id', sessionId.current); }, []);

  // ponytail: save messages to localStorage on change
  useEffect(() => { saveMessages(messages); }, [messages]);

  // ponytail: smart auto-scroll — only if user is near bottom
  useEffect(() => {
    if (!autoScrollRef.current) return;
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming, thinking]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    autoScrollRef.current = nearBottom;
  };

  const send = useCallback(() => {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: q }]);
    setLoading(true);
    setThinking('');
    setStreaming('');

    const streamingEnabled = localStorage.getItem('aura_streaming') !== 'false';
    let answer = '';
    const controller = streamReason(q, sessionId.current, (ev: StreamEvent) => {
      if (ev.type === 'thinking') {
        setThinking(ev.message || '');
      } else if (ev.type === 'result') {
        answer = ev.answer || '';
      } else if (ev.type === 'done') {
        const finalContent = streamingEnabled ? answer : (answer || streaming);
        setMessages((m) => [...m, { role: 'assistant', content: finalContent, thinking }]);
        setLoading(false);
        setThinking('');
        setStreaming('');
        abortRef.current = null;
      } else if (ev.type === 'error') {
        setMessages((m) => [...m, { role: 'assistant', content: `Error: ${ev.message}` }]);
        setLoading(false);
        setThinking('');
        setStreaming('');
        abortRef.current = null;
      }
    });
    if (controller) abortRef.current = controller;
  }, [input, loading, streaming, thinking]);

  const retry = () => {
    const last = messages[messages.length - 1];
    if (!last || last.role !== 'assistant' || loading) return;
    setMessages((m) => m.slice(0, -1));
    setInput(messages[messages.length - 2]?.content || '');
  };

  const cancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setThinking('');
    setStreaming('');
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  useEffect(() => {
    const t = textareaRef.current;
    if (t) { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; }
  }, [input]);

  const renderMsg = (m: Message, i: number) => (
    <div key={i} className={`max-w-3xl mx-auto ${m.role === 'user' ? 'text-right' : ''}`}>
      {m.thinking && <div className="text-xs text-gray-400 mb-1 italic">{m.thinking}</div>}
      <div className={`inline-block px-4 py-2 rounded-lg ${
        m.role === 'user'
          ? 'bg-blue-600 text-white'
          : 'bg-gray-200 dark:bg-gray-700 dark:text-gray-100 text-left'
      }`}>
        {m.role === 'assistant' ? (
          <Markdown
            rehypePlugins={[rehypeHighlight]}
            components={{
              code: (props) => <CodeBlock {...props} />,
              pre: ({ children }) => <pre className="overflow-x-auto">{children}</pre>,
            }}
          >{m.content}</Markdown>
        ) : m.content}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="text-center text-gray-500 mt-20">Ask AURA anything</div>
        )}
        {messages.map(renderMsg)}
        {streaming && (
          <div className="max-w-3xl mx-auto">
            <div className="inline-block px-4 py-2 rounded-lg bg-gray-200 dark:bg-gray-700 dark:text-gray-100 text-left">
              <Markdown rehypePlugins={[rehypeHighlight]} components={{
                code: (props) => <CodeBlock {...props} />,
                pre: ({ children }) => <pre className="overflow-x-auto">{children}</pre>,
              }}>{streaming}</Markdown>
            </div>
          </div>
        )}
        {loading && !streaming && thinking && (
          <div className="max-w-3xl mx-auto">
            <div className="text-xs text-gray-400 italic">{thinking}</div>
          </div>
        )}
        {loading && !streaming && !thinking && (
          <div className="max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 text-sm text-gray-400">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              Thinking...
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="border-t dark:border-gray-700 p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Type a message..."
            rows={1}
            className="flex-1 resize-none rounded-lg border dark:border-gray-600 dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {loading ? (
            <button onClick={cancel} className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm">Stop</button>
          ) : (
            <button onClick={send} disabled={!input.trim()} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">Send</button>
          )}
        </div>
        {messages.length > 0 && messages[messages.length - 1].role === 'assistant' && !loading && (
          <div className="max-w-3xl mx-auto mt-2">
            <button onClick={retry} className="text-xs text-gray-400 hover:text-gray-600">Retry last</button>
          </div>
        )}
      </div>
    </div>
  );
}
