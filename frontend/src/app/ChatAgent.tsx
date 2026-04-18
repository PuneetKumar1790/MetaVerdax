import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Download, AlertTriangle, CheckCircle, Bot, User, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api, type ChatResponse } from '../lib/api';

interface Message {
  role: 'user' | 'agent';
  content: string;
  risk_score?: string;
  report_id?: string;
}

const starters = [
  'Is my churn dataset safe to retrain?',
  'Show me all datasets with critical drift',
  'Generate compliance report for my ML pipeline',
];

export default function ChatAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: 'user', content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const data: ChatResponse = await api.chat(text.trim());
      const agentMsg: Message = {
        role: 'agent',
        content: data.response,
        risk_score: data.risk_score,
        report_id: data.report_id,
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err) {
      setError(
        'MetaVerdax Agent is starting up... check that your FastAPI backend is running on port 8000'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const getRiskBanner = (score?: string) => {
    if (!score) return null;
    const upper = score.toUpperCase();
    if (upper.includes('CRITICAL') || upper.includes('HIGH')) {
      return (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 mb-3">
          <AlertTriangle className="w-4 h-4 text-red-400 animate-pulse-critical" />
          <span className="text-xs font-semibold text-red-400">RISK SCORE: {upper}</span>
        </div>
      );
    }
    if (upper.includes('LOW') || upper.includes('APPROVED')) {
      return (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 mb-3">
          <CheckCircle className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-emerald-400">RISK SCORE: {upper}</span>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] md:h-screen">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/5">
        <h1 className="font-display text-xl font-bold text-white">Chat Agent</h1>
        <p className="text-xs text-white/30 mt-0.5">
          Ask MetaVerdax to validate your datasets and check ML readiness.
        </p>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-4">
        {/* Starters — shown when no messages */}
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="text-center">
              <Bot className="w-12 h-12 text-brand-cyan/30 mx-auto mb-4" />
              <h2 className="font-display text-lg font-bold text-white/60">
                What would you like to validate?
              </h2>
              <p className="text-sm text-white/30 mt-1">Choose a starter or type your own question.</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3 max-w-xl">
              {starters.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="px-4 py-3 rounded-xl border border-white/5 bg-white/[0.02] text-sm text-white/50 hover:text-brand-cyan hover:border-brand-cyan/20 transition-all duration-300 text-left"
                >
                  "{s}"
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'agent' && (
                <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center shrink-0 mt-1">
                  <Bot className="w-4 h-4 text-brand-cyan" />
                </div>
              )}

              <div
                className={`max-w-[80%] sm:max-w-[70%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-brand-orange/10 border border-brand-orange/20 text-white/90'
                    : 'bg-white/[0.03] border border-white/5 text-white/80'
                }`}
              >
                {msg.role === 'agent' && getRiskBanner(msg.risk_score)}
                {msg.role === 'agent' ? (
                  <div className="prose prose-invert prose-sm max-w-none [&_p]:mb-2 [&_ul]:mb-2 [&_pre]:bg-black/30 [&_pre]:rounded-lg [&_code]:text-brand-cyan">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm">{msg.content}</p>
                )}
                {msg.role === 'agent' && msg.report_id && (
                  <a
                    href={api.downloadLatestReportUrl()}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 rounded-lg border border-brand-cyan/20 text-xs font-medium text-brand-cyan hover:bg-brand-cyan/10 transition-all"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download PDF Report
                  </a>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-brand-orange/10 border border-brand-orange/20 flex items-center justify-center shrink-0 mt-1">
                  <User className="w-4 h-4 text-brand-orange" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Loading skeleton */}
        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center shrink-0">
              <Loader2 className="w-4 h-4 text-brand-cyan animate-spin" />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-white/[0.03] border border-white/5 max-w-[70%]">
              <div className="flex items-center gap-2 text-sm text-white/30">
                <span className="inline-block w-2 h-2 rounded-full bg-brand-cyan animate-pulse" />
                MetaVerdax is analyzing...
              </div>
            </div>
          </motion.div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-brand-amber/10 border border-brand-amber/20 text-sm text-brand-amber">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-4 sm:px-6 py-4 border-t border-white/5">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='Ask MetaVerdax... e.g. "Is my dataset safe to retrain?"'
            disabled={loading}
            className="flex-1 px-4 py-3 rounded-xl border border-white/10 bg-white/[0.03] text-sm text-white placeholder-white/25 focus:outline-none focus:border-brand-cyan/30 focus:ring-1 focus:ring-brand-cyan/20 transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-3 rounded-xl bg-brand-orange text-white hover:bg-brand-orange/90 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-300 hover:shadow-[0_0_20px_rgba(255,107,53,0.3)]"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
