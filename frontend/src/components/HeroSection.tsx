import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ShieldCheck } from 'lucide-react';

/* ─── Canvas Particle Background ─── */
function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let particles: {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      opacity: number;
      color: string;
    }[] = [];

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };

    const createParticles = () => {
      particles = [];
      const count = Math.min(80, Math.floor(canvas.offsetWidth / 12));
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * canvas.offsetWidth,
          y: Math.random() * canvas.offsetHeight,
          vx: (Math.random() - 0.3) * 0.8,
          vy: (Math.random() - 0.5) * 0.4,
          size: Math.random() * 2 + 0.5,
          opacity: Math.random() * 0.5 + 0.1,
          color: Math.random() > 0.5 ? '#00E5FF' : '#00B3FF',
        });
      }
    };

    const drawShield = () => {
      const cx = canvas.offsetWidth / 2;
      const cy = canvas.offsetHeight / 2 + 20;
      const r = 60;

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(cx, cy - r);
      ctx.bezierCurveTo(cx + r, cy - r, cx + r, cy + r * 0.2, cx, cy + r);
      ctx.bezierCurveTo(cx - r, cy + r * 0.2, cx - r, cy - r, cx, cy - r);
      ctx.closePath();
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.25)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = 'rgba(0, 229, 255, 0.03)';
      ctx.fill();

      ctx.shadowColor = 'rgba(0, 229, 255, 0.4)';
      ctx.shadowBlur = 30;
      ctx.stroke();
      ctx.restore();
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);

      drawShield();

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = canvas.offsetWidth;
        if (p.x > canvas.offsetWidth) p.x = 0;
        if (p.y < 0) p.y = canvas.offsetHeight;
        if (p.y > canvas.offsetHeight) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.opacity;
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      // Draw connecting lines
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(0, 229, 255, ${0.08 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animationId = requestAnimationFrame(animate);
    };

    resize();
    createParticles();
    animate();

    window.addEventListener('resize', () => {
      resize();
      createParticles();
    });

    return () => cancelAnimationFrame(animationId);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      style={{ pointerEvents: 'none' }}
    />
  );
}

/* ─── Hero Section ─── */
const headline = 'Stop Training on Bad Data.';
const subheadline =
  'MetaVerdax Agent autonomously validates, scores, and blocks ML retraining jobs — before they waste your compute and break your models.';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } },
};

const childVariants = {
  hidden: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: 'easeOut' as const },
  },
};

const badges = [
  'Powered by OpenMetadata MCP',
  'Built on FastAPI',
  'EU AI Act Ready',
];

export default function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-16">
      {/* Particle background */}
      <ParticleCanvas />

      {/* Radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_40%,rgba(0,229,255,0.06),transparent)]" />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="relative z-10 max-w-4xl mx-auto text-center px-6"
      >
        {/* Headline */}
        <motion.h1
          variants={childVariants}
          className="font-display text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-extrabold leading-[0.95] tracking-tight"
        >
          {headline.split(' ').map((word, i) => (
            <span
              key={i}
              className={
                word === 'Bad'
                  ? 'text-brand-amber'
                  : word === 'Data.'
                  ? 'text-brand-cyan'
                  : 'text-white'
              }
            >
              {word}{' '}
            </span>
          ))}
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          variants={childVariants}
          className="mt-6 text-base sm:text-lg md:text-xl text-white/60 max-w-2xl mx-auto leading-relaxed"
        >
          {subheadline}
        </motion.p>

        {/* CTAs */}
        <motion.div
          variants={childVariants}
          className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <Link
            to="/app"
            className="px-8 py-3.5 rounded-lg bg-brand-orange text-white font-semibold text-base hover:shadow-[0_0_30px_rgba(255,107,53,0.4)] hover:scale-[1.02] transition-all duration-300"
          >
            Launch Demo →
          </Link>
          <a
            href="#architecture"
            className="px-8 py-3.5 rounded-lg border border-white/10 text-white/80 font-semibold text-base hover:border-brand-cyan/40 hover:text-brand-cyan transition-all duration-300"
          >
            View Architecture
          </a>
        </motion.div>

        {/* Badges */}
        <motion.div
          variants={childVariants}
          className="mt-10 flex flex-wrap items-center justify-center gap-3"
        >
          {badges.map((badge) => (
            <span
              key={badge}
              className="px-3 py-1.5 text-xs font-medium tracking-wide text-white/40 border border-white/5 rounded-full bg-white/[0.02]"
            >
              <ShieldCheck className="w-3 h-3 inline-block mr-1 text-brand-cyan/60 -mt-0.5" />
              {badge}
            </span>
          ))}
        </motion.div>
      </motion.div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-brand-black to-transparent" />
    </section>
  );
}
