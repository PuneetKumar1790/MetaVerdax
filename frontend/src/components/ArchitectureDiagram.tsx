import { motion } from 'framer-motion';

const layers = [
  {
    label: 'Chat Interface / Dashboard',
    color: 'border-brand-cyan/30',
    bg: 'bg-brand-cyan/5',
    textColor: 'text-brand-cyan',
  },
  {
    label: 'MetaVerdax AI Engine — Groq / Gemini / Claude',
    color: 'border-blue-400/30',
    bg: 'bg-blue-400/5',
    textColor: 'text-blue-400',
  },
  {
    label: 'OpenMetadata MCP Server ↔ OpenMetadata Instance',
    color: 'border-emerald-400/30',
    bg: 'bg-emerald-400/5',
    textColor: 'text-emerald-400',
  },
  {
    label: 'Validation Core: validator.py | drift_detector.py | anomaly_scorer.py',
    color: 'border-brand-amber/30',
    bg: 'bg-brand-amber/5',
    textColor: 'text-brand-amber',
  },
  {
    label: 'Output: PDF Report | Risk Actions | Governance Tasks | Metadata Updates',
    color: 'border-brand-orange/30',
    bg: 'bg-brand-orange/5',
    textColor: 'text-brand-orange',
  },
];

export default function ArchitectureDiagram() {
  return (
    <section id="architecture" className="relative py-24 sm:py-32 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-brand-cyan text-sm font-semibold tracking-widest uppercase mb-3">
            Architecture
          </p>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white">
            Built to Production Standards
          </h2>
        </motion.div>

        {/* Diagram */}
        <div className="flex flex-col items-center gap-0">
          {layers.map((layer, i) => (
            <div key={layer.label} className="flex flex-col items-center w-full">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, margin: '-30px' }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className={`w-full max-w-2xl px-6 py-4 rounded-xl border ${layer.color} ${layer.bg} text-center`}
              >
                <p className={`text-sm sm:text-base font-mono font-medium ${layer.textColor}`}>
                  {layer.label}
                </p>
              </motion.div>

              {/* Arrow */}
              {i < layers.length - 1 && (
                <motion.div
                  initial={{ opacity: 0, scaleY: 0 }}
                  whileInView={{ opacity: 1, scaleY: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.3, delay: i * 0.1 + 0.2 }}
                  className="flex flex-col items-center py-1"
                >
                  <div className="w-px h-6 bg-gradient-to-b from-white/20 to-white/5" />
                  <svg width="12" height="8" viewBox="0 0 12 8" className="text-white/20">
                    <path d="M6 8L0 0h12L6 8z" fill="currentColor" />
                  </svg>
                </motion.div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
