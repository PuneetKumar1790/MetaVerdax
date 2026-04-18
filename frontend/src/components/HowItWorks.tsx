import { motion } from 'framer-motion';
import { MessageSquareText, Plug, ScanSearch, ShieldAlert } from 'lucide-react';

const steps = [
  {
    icon: MessageSquareText,
    title: 'Ask',
    description: 'Type a question in plain English: "Is my churn dataset safe to retrain?"',
    color: 'text-brand-cyan',
    borderColor: 'border-brand-cyan/20',
    glowColor: 'rgba(0,229,255,0.15)',
  },
  {
    icon: Plug,
    title: 'Connect',
    description: 'MCP connects to OpenMetadata, pulls lineage, schema, ownership, and history.',
    color: 'text-blue-400',
    borderColor: 'border-blue-400/20',
    glowColor: 'rgba(96,165,250,0.15)',
  },
  {
    icon: ScanSearch,
    title: 'Validate & Score',
    description: 'Runs drift detection, anomaly scoring, null checks — generates a Risk Score.',
    color: 'text-brand-amber',
    borderColor: 'border-brand-amber/20',
    glowColor: 'rgba(255,140,0,0.15)',
  },
  {
    icon: ShieldAlert,
    title: 'Block or Approve',
    description: 'Automatically blocks risky retrains, creates governance tasks, generates PDF audit report.',
    color: 'text-brand-orange',
    borderColor: 'border-brand-orange/20',
    glowColor: 'rgba(255,107,53,0.15)',
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-24 sm:py-32 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <p className="text-brand-cyan text-sm font-semibold tracking-widest uppercase mb-3">
            How It Works
          </p>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white">
            4 Steps to Autonomous Governance
          </h2>
        </motion.div>

        {/* Steps */}
        <div className="relative grid grid-cols-1 md:grid-cols-4 gap-8 md:gap-4">
          {/* Connecting line — desktop only */}
          <div className="hidden md:block absolute top-12 left-[12.5%] right-[12.5%] h-px bg-gradient-to-r from-brand-cyan/20 via-brand-amber/20 to-brand-orange/20" />

          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-30px' }}
                transition={{ duration: 0.5, delay: i * 0.15, ease: [0.22, 1, 0.36, 1] }}
                className="relative flex flex-col items-center text-center"
              >
                {/* Step number */}
                <div
                  className={`relative z-10 w-20 h-20 rounded-2xl border ${step.borderColor} bg-brand-black flex items-center justify-center mb-5`}
                  style={{ boxShadow: `0 0 30px ${step.glowColor}` }}
                >
                  <Icon className={`w-8 h-8 ${step.color}`} />
                </div>
                <span className="text-xs text-white/30 font-mono mb-1">0{i + 1}</span>
                <h3 className={`font-display text-lg font-bold ${step.color} mb-2`}>
                  {step.title}
                </h3>
                <p className="text-sm text-white/50 leading-relaxed max-w-[240px]">
                  {step.description}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
