import { motion } from 'framer-motion';
import { Search, GitBranch, ClipboardCheck, ShieldCheck, ArrowRight } from 'lucide-react';

const capabilities = [
  {
    icon: Search,
    title: 'Metadata Discovery',
    description: "Agent queries OpenMetadata's knowledge graph in real-time to understand your data landscape.",
  },
  {
    icon: GitBranch,
    title: 'Lineage Traversal',
    description: 'Automatically maps all downstream assets at risk when upstream data quality degrades.',
  },
  {
    icon: ClipboardCheck,
    title: 'Governance Actions',
    description: 'Creates tasks, assigns owners, updates quality flags — all autonomously via MCP.',
  },
];

export default function OpenMetadataMCP() {
  return (
    <section className="relative py-24 sm:py-32 px-6 overflow-hidden">
      {/* Background accent */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-brand-cyan/[0.02] to-transparent" />

      <div className="relative max-w-6xl mx-auto">
        {/* Logos + Bridge */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-6 mb-12"
        >
          {/* OpenMetadata Logo */}
          <div className="px-6 py-3 rounded-xl border border-white/10 bg-white/[0.02]">
            <span className="font-display text-lg font-bold text-white">OpenMetadata</span>
          </div>

          {/* Connection arrow */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-px bg-gradient-to-r from-white/20 to-brand-cyan/50" />
            <ArrowRight className="w-5 h-5 text-brand-cyan animate-pulse" />
            <div className="w-8 h-px bg-gradient-to-r from-brand-cyan/50 to-white/20" />
          </div>

          {/* MetaVerdax Logo */}
          <div className="px-6 py-3 rounded-xl border border-brand-cyan/20 bg-brand-cyan/[0.03]">
            <ShieldCheck className="w-5 h-5 inline-block mr-2 text-brand-cyan -mt-0.5" />
            <span className="font-display text-lg font-bold text-brand-cyan">MetaVerdax</span>
          </div>
        </motion.div>

        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-center mb-6"
        >
          <p className="text-brand-cyan text-sm font-semibold tracking-widest uppercase mb-3">
            Powered by OpenMetadata MCP
          </p>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white">
            The Integration That Changes Everything
          </h2>
        </motion.div>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-center text-white/50 max-w-3xl mx-auto mb-16 text-base sm:text-lg leading-relaxed"
        >
          OpenMetadata's MCP server exposes metadata operations as tools that the AI agent can invoke
          directly — no manual API calls, no hard-coded queries. The agent discovers lineage, ownership,
          quality metrics, and schema changes autonomously through natural language.
        </motion.p>

        {/* Capability Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {capabilities.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <motion.div
                key={cap.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-30px' }}
                transition={{ duration: 0.5, delay: i * 0.12 }}
                className="group relative p-6 sm:p-8 rounded-2xl border border-white/5 bg-white/[0.02] hover:border-brand-cyan/20 transition-all duration-500"
              >
                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-brand-cyan/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative z-10">
                  <div className="w-12 h-12 rounded-xl border border-brand-cyan/20 flex items-center justify-center mb-4 bg-brand-cyan/[0.05]">
                    <Icon className="w-6 h-6 text-brand-cyan" />
                  </div>
                  <h3 className="font-display text-lg font-bold text-white mb-2">{cap.title}</h3>
                  <p className="text-sm text-white/50 leading-relaxed">{cap.description}</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Note */}
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-12 text-center text-sm text-white/30 italic"
        >
          OpenMetadata MCP is the reason MetaVerdax can <span className="text-brand-cyan/60">act</span>, not just observe.
        </motion.p>
      </div>
    </section>
  );
}
