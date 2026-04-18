import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Clock, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { api, type ValidationHistoryItem } from '../lib/api';

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toISOString().replace('T', ' ').slice(0, 16);
}

function RiskBadge({ score }: { score: string }) {
  const upper = score.toUpperCase();
  if (upper.includes('CRITICAL')) {
    return (
      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-red-500/15 text-red-400 border border-red-500/20 animate-pulse-critical">
        CRITICAL
      </span>
    );
  }
  if (upper.includes('HIGH')) {
    return (
      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-brand-amber/15 text-brand-amber border border-brand-amber/20">
        HIGH
      </span>
    );
  }
  return (
    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
      LOW
    </span>
  );
}

export default function ValidationHistory() {
  const [history, setHistory] = useState<ValidationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await api.getHistory();
        setHistory(data);
      } catch {
        setError('Unable to fetch validation history. Is your backend running?');
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold text-white">Validation History</h1>
        <p className="text-base text-white/30 mt-1">
          Past dataset validations and their risk assessments.
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-brand-cyan animate-spin" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-brand-amber/10 border border-brand-amber/20 text-sm text-brand-amber">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {!loading && !error && history.length === 0 && (
        <div className="text-center py-20 text-white/20">
          <Clock className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No validation history yet. Run a validation from the Chat Agent.</p>
        </div>
      )}

      {!loading && !error && history.length > 0 && (
        <div className="rounded-2xl border border-white/5 overflow-hidden">
          {/* Table header */}
          <div className="hidden sm:grid sm:grid-cols-[minmax(0,2fr)_110px_160px_140px_24px] gap-3 px-6 py-3 bg-white/[0.02] border-b border-white/5 text-sm font-semibold text-white/40 uppercase tracking-wider">
            <span>Dataset</span>
            <span>Risk Score</span>
            <span>Timestamp</span>
            <span>Action</span>
            <span></span>
          </div>

          {/* Rows */}
          {history.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="border-b border-white/[0.03] last:border-b-0"
            >
              <div
                className="grid grid-cols-1 sm:grid-cols-[minmax(0,2fr)_110px_160px_140px_24px] gap-2 sm:gap-3 px-6 py-4 hover:bg-white/[0.02] transition-colors cursor-pointer items-center"
                onClick={() =>
                  setExpandedId(expandedId === item.id ? null : item.id)
                }
              >
                <span className="text-base text-white/85 font-medium min-w-0 truncate" title={item.dataset}>{item.dataset}</span>
                <span className="sm:justify-self-start"><RiskBadge score={item.risk_score} /></span>
                <span className="text-sm text-white/40 font-mono whitespace-nowrap">{formatTimestamp(item.timestamp)}</span>
                <span className="text-sm text-white/60 whitespace-nowrap">{item.action}</span>
                <span className="flex justify-end">
                  {expandedId === item.id ? (
                    <ChevronUp className="w-4 h-4 text-white/20" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-white/20" />
                  )}
                </span>
              </div>

              {/* Expanded detail */}
              {expandedId === item.id && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="px-6 pb-4"
                >
                  <div className="rounded-xl bg-white/[0.02] border border-white/5 p-4 text-sm text-white/50">
                    <p><strong className="text-white/70">Dataset:</strong> {item.dataset}</p>
                    <p><strong className="text-white/70">Risk Score:</strong> {item.risk_score}</p>
                    <p><strong className="text-white/70">Action:</strong> {item.action}</p>
                    {item.report_url && (
                      <a
                        href={api.downloadReportUrl(item.report_url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 mt-2 text-brand-cyan text-xs hover:underline"
                      >
                        <CheckCircle className="w-3 h-3" /> Download Report
                      </a>
                    )}
                  </div>
                </motion.div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
