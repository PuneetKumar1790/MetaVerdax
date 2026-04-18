import { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';

interface StatCardProps {
  numericValue: number;
  prefix?: string;
  suffix?: string;
  label: string;
  source: string;
  index: number;
}

function AnimatedCounter({ target, prefix = '', suffix = '' }: { target: number; prefix?: string; suffix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-50px' });

  useEffect(() => {
    if (!inView) return;
    const duration = 2000;
    const start = Date.now();
    const step = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [inView, target]);

  return <span ref={ref}>{prefix}{count}{suffix}</span>;
}

function StatCard({ numericValue, prefix, suffix, label, source, index }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.6, delay: index * 0.12, ease: 'easeOut' }}
      className="relative group p-6 sm:p-8 rounded-2xl border border-white/5 bg-white/[0.02] hover:border-brand-amber/20 transition-all duration-500"
    >
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-brand-amber/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      <div className="relative z-10">
        <p className="font-display text-4xl sm:text-5xl font-extrabold text-brand-amber tracking-tight">
          <AnimatedCounter target={numericValue} prefix={prefix} suffix={suffix} />
        </p>
        <p className="mt-2 text-white/80 font-semibold text-sm sm:text-base">{label}</p>
        <p className="mt-1 text-white/30 text-xs">Source: {source}</p>
      </div>
    </motion.div>
  );
}

const stats = [
  { value: '60–80%', numericValue: 80, suffix: '%', label: "Data Scientists' time wasted on cleaning", source: 'Appen' },
  { value: '$100K+', numericValue: 100, prefix: '$', suffix: 'K+', label: 'Average cost of one bad GPU retraining run', source: 'Gartner' },
  { value: '$25M/yr', numericValue: 25, prefix: '$', suffix: 'M', label: 'Annual data quality losses per enterprise', source: 'Forrester' },
  { value: '€35M', numericValue: 35, prefix: '€', suffix: 'M', label: 'Max EU AI Act fine for governance failures', source: 'EU AI Act' },
];

export default function ProblemSection() {
  return (
    <section className="relative py-24 sm:py-32 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Section Heading */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-brand-amber text-sm font-semibold tracking-widest uppercase mb-3">
            The Data Governance Crisis
          </p>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white">
            Bad Data is Silently Destroying Your AI.
          </h2>
        </motion.div>

        {/* 2x2 Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
          {stats.map((stat, i) => (
            <StatCard key={stat.value} {...stat} index={i} />
          ))}
        </div>

        {/* Callout */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="mt-16 text-center text-xl sm:text-2xl md:text-3xl font-display font-bold text-white/70"
        >
          And most companies still retrain{' '}
          <span className="text-brand-amber">blindly</span>.
        </motion.p>
      </div>
    </section>
  );
}
