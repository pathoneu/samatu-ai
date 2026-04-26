/**
 * AiChat — natural language Q&A apie projektą.
 *
 * Apačioje dešinėje — floating chat button. Atidarius — panel su istoriniais
 * klausimais ir input'u. Backend kvietimas /chat-project.
 *
 * Pavyzdiniai klausimai:
 * - "Kiek dušų projekte?"
 * - "Kuris kambarys didžiausias?"
 * - "Ar yra langų virtuvėje?"
 * - "Koks bendras dažomas plotas pirmame aukšte?"
 */

import { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Loader2, Sparkles } from 'lucide-react';

const SUGGESTED_QUESTIONS = [
  'Kuris kambarys didžiausias?',
  'Kiek bendrai dušo zonų?',
  'Koks visas dažomas plotas?',
  'Ar yra patalpų virš 3m aukščio?',
];

export default function AiChat({ project, inline = false }) {
  // inline=true → embed mode (tab content); inline=false → floating widget
  const [open, setOpen] = useState(inline);  // inline mode = always open
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const ask = async (question) => {
    if (!question.trim() || loading) return;
    const userMsg = { role: 'user', text: question };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/chat-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          project_context: {
            name: project?.name,
            v8_rooms: project?.v8_rooms,
            v8_totals: project?.v8_totals,
            darbu_sarasas: project?.darbu_sarasas,
          },
        }),
      });
      const json = await res.json();
      if (json.status === 'ok') {
        setMessages(prev => [...prev, { role: 'ai', text: json.answer }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'ai', text: `Klaida: ${json.error || 'nežinoma'}`, isError: true,
        }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'ai', text: `Tinklo klaida: ${e.message}`, isError: true,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    ask(input);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-2.5 bg-foreground text-background rounded-lg shadow-md hover:shadow-lg transition-shadow"
        title="Klauskite AI apie projektą"
      >
        <MessageCircle className="w-4 h-4" />
        <span className="text-sm font-medium">AI</span>
      </button>
    );
  }

  // Layout — inline mode (tab embedded) vs floating widget
  const containerClass = inline
    ? "w-full h-[600px] bg-card rounded-xl border border-border flex flex-col overflow-hidden"
    : "fixed bottom-6 right-6 z-40 w-96 max-w-[calc(100vw-3rem)] h-[500px] max-h-[calc(100vh-6rem)] bg-card rounded-xl shadow-2xl border border-border flex flex-col overflow-hidden";

  return (
    <div className={containerClass}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-muted/50 border-b border-border">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">AI projekto pagalbininkas</span>
        </div>
        {!inline && (
          <button onClick={() => setOpen(false)}
            className="p-1 hover:bg-muted rounded text-muted-foreground">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 bg-background">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground text-sm py-4">
            <Sparkles className="w-6 h-6 mx-auto mb-2 text-muted-foreground/60" />
            <p className="mb-3">Klauskite ką nors apie projektą</p>
            <div className="space-y-1.5">
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => ask(q)}
                  className="block w-full text-left text-xs px-3 py-1.5 bg-card border border-border rounded-lg hover:border-foreground/30 hover:bg-muted/50 transition-colors text-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-lg text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-foreground text-background'
                  : m.isError
                    ? 'bg-destructive/10 border border-destructive/20 text-destructive'
                    : 'bg-card border border-border text-foreground'
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-card border border-border px-3 py-2 rounded-lg flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Galvoju...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-border bg-card">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Kiek dušų projekte?"
            disabled={loading}
            className="flex-1 px-3 py-2 border border-border bg-background rounded-lg text-sm focus:outline-none focus:border-foreground/40 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-3 py-2 bg-foreground text-background hover:opacity-90 disabled:opacity-30 rounded-lg"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
