import { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { Link } from 'react-router-dom';

const terminalLines = [
  { type: 'user', text: '> Is my customer_churn_v3.csv safe for model retraining?' },
  { type: 'agent', text: '' },
  { type: 'agent', text: 'MetaVerdax Agent: Connecting to OpenMetadata via MCP...' },
  { type: 'success', text: '✓ Pulled schema history (14 versions)' },
  { type: 'success', text: '✓ Lineage graph: 8 downstream assets identified' },
  { type: 'warning', text: '⚠ Running validation suite...' },
  { type: 'agent', text: '' },
  { type: 'agent', text: 'FINDINGS:' },
  { type: 'agent', text: '• Missing values jumped 18% vs baseline' },
  { type: 'agent', text: '• Duplicate records spike detected (+340%)' },
  { type: 'agent', text: '• Distribution drift: CRITICAL (KS stat > 0.3)' },
  { type: 'agent', text: '• 3 outlier clusters outside training distribution' },
  { type: 'agent', text: '' },
  { type: 'divider', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
  { type: 'critical', text: 'RISK SCORE: CRITICAL 🔴' },
  { type: 'divider', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
  { type: 'agent', text: '' },
  { type: 'action', text: 'ACTION: Retraining job BLOCKED' },
  { type: 'action', text: 'Governance task created → assigned to @data-steward' },
  { type: 'action', text: '8 downstream pipelines flagged for review' },
  { type: 'success', text: 'PDF audit report generated ✓' },
];

function getLineColor(type: string): string {
  switch (type) {
    case 'user': return 'text-brand-cyan';
    case 'success': return 'text-emerald-400';
    case 'warning': return 'text-brand-amber';
    case 'critical': return 'text-red-400 font-bold';
    case 'action': return 'text-brand-orange';
    case 'divider': return 'text-white/20';
    default: return 'text-white/70';
  }
}

export default function DemoTerminal() {
  const [visibleLines, setVisibleLines] = useState(0);
  const [currentText, setCurrentText] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-100px' });
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!inView) return;

    let lineIndex = 0;
    let charIndex = 0;
    let timeout: ReturnType<typeof setTimeout>;

    const typeLine = () => {
      if (lineIndex >= terminalLines.length) return;

      const line = terminalLines[lineIndex];

      if (line.text === '' || line.type === 'divider') {
        setVisibleLines(lineIndex + 1);
        setCurrentText('');
        lineIndex++;
        timeout = setTimeout(typeLine, 200);
        return;
      }

      if (charIndex < line.text.length) {
        setCurrentText(line.text.slice(0, charIndex + 1));
        charIndex++;
        timeout = setTimeout(typeLine, 25);
      } else {
        setVisibleLines(lineIndex + 1);
        setCurrentText('');
        lineIndex++;
        charIndex = 0;
        timeout = setTimeout(typeLine, 150);
      }
    };

    timeout = setTimeout(typeLine, 600);
    return () => clearTimeout(timeout);
  }, [inView]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visibleLines, currentText]);

  return (
    <section id="demo" className="relative py-24 sm:py-32 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <p className="text-brand-cyan text-sm font-semibold tracking-widest uppercase mb-3">
            Live Demo Preview
          </p>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white">
            See It Catch a Critical Failure
          </h2>
        </motion.div>

        {/* Terminal */}
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="relative rounded-2xl border border-white/10 bg-[#0c0c0c] overflow-hidden shadow-2xl shadow-brand-cyan/5"
        >
          {/* Terminal header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 bg-white/[0.02]">
            <div className="w-3 h-3 rounded-full bg-red-500/70" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
            <span className="ml-3 text-xs text-white/30 font-mono">metaverdax-agent</span>
          </div>

          {/* Terminal body */}
          <div
            ref={scrollRef}
            className="p-5 sm:p-6 font-mono text-xs sm:text-sm leading-relaxed h-[420px] overflow-y-auto"
          >
            {terminalLines.slice(0, visibleLines).map((line, i) => (
              <div
                key={i}
                className={`${getLineColor(line.type)} ${line.text === '' ? 'h-4' : ''}`}
              >
                {line.text}
              </div>
            ))}
            {visibleLines < terminalLines.length && currentText && (
              <div className={getLineColor(terminalLines[visibleLines]?.type || 'agent')}>
                {currentText}
                <span className="terminal-cursor">▊</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="text-center mt-8"
        >
          <Link
            to="/app"
            className="inline-flex px-8 py-3.5 rounded-lg bg-brand-orange text-white font-semibold text-base hover:shadow-[0_0_30px_rgba(255,107,53,0.4)] hover:scale-[1.02] transition-all duration-300"
          >
            Try Live Demo →
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
