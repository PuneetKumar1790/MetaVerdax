import { motion } from 'framer-motion';
import { Check, X } from 'lucide-react';

const features = [
  { feature: 'Interface', traditional: 'Manual SQL queries', metaverdax: 'Natural language AI' },
  { feature: 'Scope', traditional: 'Separate dashboards', metaverdax: 'Governance + observability unified' },
  { feature: 'Response', traditional: 'Reactive alerts', metaverdax: 'Proactive blocking' },
  { feature: 'Setup', traditional: 'Complex configuration', metaverdax: 'MCP auto-discovery' },
  { feature: 'ML Safety', traditional: 'No automated blocking', metaverdax: 'Risk-scored retrain gating' },
  { feature: 'Compliance', traditional: 'Manual reports', metaverdax: 'Auto-generated PDF audit trail' },
  { feature: 'Carbon', traditional: 'Not tracked', metaverdax: 'Carbon savings estimated' },
];

export default function ComparisonTable() {
  return (
    <section className="relative py-24 sm:py-32 px-6">
      <div className="max-w-5xl mx-auto">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-brand-cyan text-sm font-semibold tracking-widest uppercase mb-3">
            Why MetaVerdax Wins
          </p>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white">
            Not Another Dashboard.
          </h2>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-brand-cyan mt-1">
            An Autonomous Trust Layer.
          </h2>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="rounded-2xl border border-white/5 overflow-hidden"
        >
          {/* Header row */}
          <div className="grid grid-cols-3 bg-white/[0.03] border-b border-white/5">
            <div className="px-4 sm:px-6 py-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Feature</div>
            <div className="px-4 sm:px-6 py-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Traditional Tools</div>
            <div className="px-4 sm:px-6 py-4 text-xs font-semibold text-brand-cyan uppercase tracking-wider">MetaVerdax Agent</div>
          </div>

          {/* Rows */}
          {features.map((row, i) => (
            <div
              key={row.feature}
              className={`grid grid-cols-3 border-b border-white/[0.03] ${
                i % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.01]'
              } hover:bg-white/[0.03] transition-colors duration-300`}
            >
              <div className="px-4 sm:px-6 py-4 text-sm font-medium text-white/80">
                {row.feature}
              </div>
              <div className="px-4 sm:px-6 py-4 text-sm text-white/40 flex items-center gap-2">
                <X className="w-3.5 h-3.5 text-red-400/60 shrink-0" />
                {row.traditional}
              </div>
              <div className="px-4 sm:px-6 py-4 text-sm text-brand-cyan/90 flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-brand-cyan shrink-0" />
                {row.metaverdax}
              </div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
