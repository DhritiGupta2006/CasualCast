import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "wouter";
import { motion, useInView, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SimulationTheater from "@/components/SimulationTheater";
import {
  ArrowRight,
  Gauge,
  LineChart as LineChartIcon,
  GitBranch,
  ShieldCheck,
  Layers,
  Sparkles,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Signature hero element: an animated "probability cone" — a single  */
/* revenue line that fans out into a widening P10/P50/P90 band. This  */
/* is a literal picture of the product's core idea, not a decoration. */
/* ------------------------------------------------------------------ */

function seededRandom(seed: number) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return function () {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}
function boxMuller(rand: () => number) {
  let u = 0,
    v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function buildCone(seed: number) {
  const points = 40;
  const rand = seededRandom(seed);
  const hist: number[] = [];
  let v = 50;
  for (let i = 0; i < 16; i++) {
    v += boxMuller(rand) * 3;
    hist.push(v);
  }
  const fx = (i: number) => 40 + (i / points) * 520;
  const fyMid = (val: number) => 200 - val * 1.4;
  let midPath = `M ${fx(0)} ${fyMid(hist[0])}`;
  hist.forEach((h, i) => {
    midPath += ` L ${fx(i)} ${fyMid(h)}`;
  });

  // A swarm of faint individual Monte Carlo paths, literally showing the
  // simulations that make up the band, not just its outer edge.
  const swarm: string[] = [];
  for (let s = 0; s < 14; s++) {
    const srand = seededRandom(seed * 97 + s * 13 + 1);
    let last = hist[hist.length - 1];
    let d = `M ${fx(16)} ${fyMid(last)}`;
    for (let i = 1; i <= points - 16; i++) {
      last += 1.1 + boxMuller(srand) * (1 + i * 0.35);
      d += ` L ${fx(16 + i)} ${fyMid(last)}`;
    }
    swarm.push(d);
  }

  const upper: number[] = [],
    lower: number[] = [],
    mid: number[] = [];
  let last = hist[hist.length - 1];
  for (let i = 0; i < points - 16; i++) {
    last += 1.1;
    const spread = 3 + i * 1.15;
    upper.push(last + spread);
    lower.push(last - spread);
    mid.push(last);
  }
  let fanUpper = `L ${fx(16)} ${fyMid(hist[15])}`;
  upper.forEach((u, i) => {
    fanUpper += ` L ${fx(16 + i)} ${fyMid(u)}`;
  });
  let fanLower = "";
  lower
    .slice()
    .reverse()
    .forEach((l, i) => {
      const idx = 16 + (lower.length - 1 - i);
      fanLower += ` L ${fx(idx)} ${fyMid(l)}`;
    });
  const fanArea = `${fanUpper} ${fanLower} Z`;
  let midLine = `M ${fx(16)} ${fyMid(hist[15])}`;
  mid.forEach((m, i) => {
    midLine += ` L ${fx(16 + i)} ${fyMid(m)}`;
  });

  return { midPath, fanArea, midLine, swarm };
}

function ProbabilityCone() {
  const [seed, setSeed] = useState(3);
  const [spinning, setSpinning] = useState(false);
  const path = useMemo(() => buildCone(seed), [seed]);

  const reroll = () => {
    setSpinning(true);
    setSeed((s) => s + 1);
    window.setTimeout(() => setSpinning(false), 700);
  };

  return (
    <div>
      <svg viewBox="0 0 600 220" className="w-full h-auto">
        <defs>
          <linearGradient id="coneFill" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0.03" />
          </linearGradient>
        </defs>
        <line x1="40" y1="200" x2="560" y2="200" stroke="var(--border)" strokeWidth="1" />
        <path d={path.midPath} fill="none" stroke="var(--muted-foreground)" strokeWidth="2" opacity="0.6" />

        <AnimatePresence mode="wait">
          <motion.g key={seed}>
            {path.swarm.map((d, i) => (
              <motion.path
                key={i}
                d={d}
                fill="none"
                stroke="var(--chart-1)"
                strokeWidth="1"
                initial={{ opacity: 0, pathLength: 0 }}
                animate={{ opacity: 0.16, pathLength: 1 }}
                transition={{ duration: 0.9, delay: i * 0.03, ease: "easeOut" }}
              />
            ))}
            <motion.path
              d={path.fanArea}
              fill="url(#coneFill)"
              stroke="none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 1, delay: 0.2 }}
            />
            <motion.path
              d={path.midLine}
              fill="none"
              stroke="var(--chart-1)"
              strokeWidth="2.5"
              strokeLinecap="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.2, ease: "easeInOut" }}
            />
          </motion.g>
        </AnimatePresence>

        <line x1="260" y1="10" x2="260" y2="200" stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
        <text x="264" y="24" fill="var(--muted-foreground)" fontSize="11" className="font-mono-data">
          today
        </text>
        <text x="500" y="55" fill="var(--chart-3)" fontSize="11" className="font-mono-data">
          P90
        </text>
        <text x="500" y="185" fill="var(--chart-2)" fontSize="11" className="font-mono-data">
          P10
        </text>
      </svg>
      <div className="flex items-center justify-between mt-2">
        <p className="text-xs text-center text-muted-foreground/70 font-mono-data">
          14 of 1,000 simulated paths shown · widening uncertainty over the 30-day horizon
        </p>
        <button
          onClick={reroll}
          className="shrink-0 ml-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors font-mono-data"
          aria-label="Re-run simulation"
        >
          <motion.span animate={{ rotate: spinning ? 360 : 0 }} transition={{ duration: 0.7, ease: "easeInOut" }}>
            <RefreshCw size={12} />
          </motion.span>
          re-run
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Lightweight count-up used in the live stats strip under the hero.  */
/* ------------------------------------------------------------------ */

function CountUp({ to, suffix = "", decimals = 0 }: { to: number; suffix?: string; decimals?: number }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const duration = 1100;
    const start = performance.now();
    let raf: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(to * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to]);

  return (
    <span ref={ref} className="font-mono-data tabular-nums">
      {val.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/* ------------------------------------------------------------------ */

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay }}
    >
      {children}
    </motion.div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  desc,
  delay,
}: {
  icon: React.ElementType;
  title: string;
  desc: string;
  delay: number;
}) {
  return (
    <Reveal delay={delay}>
      <div className="rounded-xl border border-border bg-card p-6 h-full transition-all duration-300 hover:-translate-y-1 hover:border-primary/40">
        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center mb-4">
          <Icon size={18} className="text-primary" />
        </div>
        <h3 className="text-base font-semibold mb-2 text-foreground">{title}</h3>
        <p className="text-sm leading-relaxed text-muted-foreground">{desc}</p>
      </div>
    </Reveal>
  );
}

function StepRow({ n, title, desc, last = false }: { n: string; title: string; desc: string; last?: boolean }) {
  return (
    <Reveal>
      <div className="flex gap-5">
        <div className="flex flex-col items-center">
          <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm shrink-0 bg-muted text-primary border border-border font-mono-data">
            {n}
          </div>
          {!last && <div className="w-px flex-1 mt-1 bg-border" />}
        </div>
        <div className="pb-10">
          <h4 className="text-base font-semibold mb-1.5 text-foreground">{title}</h4>
          <p className="text-sm leading-relaxed max-w-md text-muted-foreground">{desc}</p>
        </div>
      </div>
    </Reveal>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
          <div
            className="absolute -top-24 -left-24 w-[26rem] h-[26rem] rounded-full blur-3xl animate-orb-a"
            style={{ background: "radial-gradient(circle, var(--chart-1) 0%, transparent 70%)", opacity: 0.16 }}
          />
          <div
            className="absolute top-10 right-[-6rem] w-[22rem] h-[22rem] rounded-full blur-3xl animate-orb-b"
            style={{ background: "radial-gradient(circle, var(--chart-2) 0%, transparent 70%)", opacity: 0.14 }}
          />
          <div
            className="absolute inset-0 dot-grid-bg opacity-[0.35]"
            style={{ maskImage: "radial-gradient(ellipse 60% 50% at 50% 20%, black, transparent)" }}
          />
        </div>

      <div className="container max-w-6xl mx-auto pt-16 pb-8 md:pt-24 md:pb-12 grid md:grid-cols-2 gap-12 items-center">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full mb-6 border border-border text-muted-foreground font-mono-data"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            MONTE CARLO · 1,000 SIMULATIONS
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-4xl md:text-5xl mb-6 text-foreground"
          >
            Forecast revenue with defensible confidence.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-base leading-relaxed mb-8 max-w-md text-muted-foreground"
          >
            CausalCast turns your spend and revenue history into P10 / P50 / P90
            forecasts — honest ranges instead of a single confident-sounding
            number, and incrementality signals clearly labeled as directional,
            not proven.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-wrap gap-3"
          >
            <Button asChild size="lg" className="font-medium">
              <Link href="/forecast">
                Run a forecast <ArrowRight size={15} />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <a href="#trust">How it's honest</a>
            </Button>
          </motion.div>
        </div>
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="rounded-2xl p-5 border border-border bg-card"
        >
          <ProbabilityCone />
        </motion.div>
      </div>
      </section>

      {/* LIVE STATS STRIP */}
      <section className="border-y border-border bg-card/40">
        <div className="container max-w-6xl mx-auto py-8 grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { to: 1000, suffix: "", label: "simulated paths per run" },
            { to: 30, suffix: "d", label: "forecast horizon" },
            { to: 3, suffix: "", label: "confidence bands (P10/P50/P90)" },
            { to: 0, suffix: "", label: "rows uploaded to our servers", isZero: true },
          ].map((s, i) => (
            <Reveal key={s.label} delay={i * 0.05}>
              <div className="text-center md:text-left">
                <div className="text-2xl md:text-3xl font-semibold text-foreground">
                  {s.isZero ? "0" : <CountUp to={s.to} suffix={s.suffix} />}
                </div>
                <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section className="container max-w-6xl mx-auto py-20">
        <Reveal>
          <div className="mb-10 max-w-lg">
            <div className="text-xs uppercase tracking-wider mb-3 text-primary font-mono-data">Capabilities</div>
            <h2 className="text-2xl md:text-3xl text-foreground">
              Everything you need to plan a budget, nothing you need to defend later.
            </h2>
          </div>
        </Reveal>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <FeatureCard
            icon={Gauge}
            title="P10 / P50 / P90 forecasts"
            desc="Every forecast ships as a range, not a point estimate — so you can plan for the downside and still sell the upside."
            delay={0}
          />
          <FeatureCard
            icon={LineChartIcon}
            title="Monte Carlo simulation"
            desc="1,000 simulated revenue paths per forecast, built from trend, weekday seasonality, and historical volatility."
            delay={0.05}
          />
          <FeatureCard
            icon={GitBranch}
            title="Multi-channel awareness"
            desc="Feed in spend, sessions, and revenue together to see how they move relative to one another over time."
            delay={0.1}
          />
          <FeatureCard
            icon={ShieldCheck}
            title="Correlation, labeled honestly"
            desc="Incrementality signals are always flagged as directional and correlation-based — never dressed up as proven causation."
            delay={0.15}
          />
          <FeatureCard
            icon={Layers}
            title="Confidence bands, visualized"
            desc="Combined, forecast-only, and band views so stakeholders can read the uncertainty at a glance, not just the median."
            delay={0.2}
          />
          <FeatureCard
            icon={Sparkles}
            title="Ready-to-share exports"
            desc="One-click CSV export and a print-ready report view for the numbers that need to leave this tab."
            delay={0.25}
          />
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="method" className="container max-w-6xl mx-auto py-16 grid md:grid-cols-2 gap-16 scroll-mt-20">
        <div>
          <Reveal>
            <div className="text-xs uppercase tracking-wider mb-3 text-primary font-mono-data">Method</div>
            <h2 className="text-2xl md:text-3xl mb-8 text-foreground">From spreadsheet to forecast in four steps.</h2>
          </Reveal>
          <StepRow n="1" title="Bring your history" desc="Upload a CSV or Excel file, paste rows directly, or load sample data to see the tool work first." />
          <StepRow n="2" title="Map your columns" desc="CausalCast auto-detects date, spend, revenue, and sessions — with a manual mapping step if your headers differ." />
          <StepRow n="3" title="Simulate the future" desc="A trend and weekday-seasonality model runs 1,000 Monte Carlo paths across a 30-day horizon." />
          <StepRow n="4" title="Read the range, not just the number" desc="Compare P10, P50, and P90 outcomes, then export the numbers that go into your next budget conversation." last />
        </div>
        <Reveal delay={0.1}>
          <div className="rounded-2xl border border-border bg-card p-6 flex flex-col justify-center h-full">
            <div className="text-xs uppercase tracking-wider mb-4 text-muted-foreground/70 font-mono-data">
              Sample output
            </div>
            {[
              ["Downside · P10", "$41,200", "var(--chart-2)"],
              ["Expected · P50", "$52,800", "var(--chart-1)"],
              ["Upside · P90", "$66,900", "var(--chart-3)"],
            ].map(([label, val, c]) => (
              <div key={label} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                <span className="text-sm text-muted-foreground">{label}</span>
                <span className="text-lg font-semibold font-mono-data" style={{ color: c }}>
                  {val}
                </span>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* SIMULATION THEATER — the moving picture */}
      <section className="container max-w-6xl mx-auto py-4 pb-16">
        <Reveal>
          <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
            <div>
              <div className="text-xs uppercase tracking-wider mb-3 text-primary font-mono-data">Live</div>
              <h2 className="text-2xl md:text-3xl text-foreground">1,000 futures, running in real time.</h2>
            </div>
            <p className="text-sm text-muted-foreground max-w-sm">
              This isn't a screenshot — it's the actual simulation loop, restyled and slowed down so you can watch
              individual Monte Carlo paths get born, diverge, and scroll off into the forecast horizon.
            </p>
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            <SimulationTheater className="h-[260px] md:h-[320px]" />
          </div>
        </Reveal>
      </section>

      {/* TRUST */}
      <section id="trust" className="container max-w-6xl mx-auto py-20 scroll-mt-20">
        <Reveal>
          <div className="mb-10 max-w-lg">
            <div className="text-xs uppercase tracking-wider mb-3 text-primary font-mono-data">Trust</div>
            <h2 className="text-2xl md:text-3xl text-foreground">What we claim, and what we deliberately don't.</h2>
          </div>
        </Reveal>
        <div className="grid md:grid-cols-2 gap-5">
          <Reveal>
            <div className="rounded-xl border border-border bg-card p-6 h-full">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 size={18} className="text-primary" />
                <h3 className="text-base font-semibold text-foreground">We claim</h3>
              </div>
              {[
                "Statistically grounded revenue ranges from your own historical data",
                "Transparent methodology you can inspect and explain to stakeholders",
                "Directional read on which channels correlate with revenue movement",
              ].map((t) => (
                <p key={t} className="text-sm leading-relaxed mb-3 text-muted-foreground">
                  {t}
                </p>
              ))}
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="rounded-xl border border-border bg-card p-6 h-full">
              <div className="flex items-center gap-2 mb-4">
                <XCircle size={18} className="text-destructive" />
                <h3 className="text-base font-semibold text-foreground">We don't claim</h3>
              </div>
              {[
                "Proof that any single channel caused a revenue outcome",
                "Certainty — every forecast is a range that can and will be wrong sometimes",
                "That 30 days of data can predict a black-swan quarter",
              ].map((t) => (
                <p key={t} className="text-sm leading-relaxed mb-3 text-muted-foreground">
                  {t}
                </p>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="container max-w-6xl mx-auto py-16">
        <Reveal>
          <div className="relative rounded-2xl border border-border p-10 md:p-14 text-center bg-gradient-to-br from-card to-muted overflow-hidden">
            <div
              className="pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[30rem] h-[20rem] rounded-full blur-3xl animate-orb-a"
              style={{ background: "radial-gradient(circle, var(--chart-1) 0%, transparent 70%)", opacity: 0.18 }}
              aria-hidden="true"
            />
            <div className="relative">
              <h2 className="text-2xl md:text-3xl mb-4 text-foreground">
                Bring your last 14+ days of data. Get a defensible 30-day range.
              </h2>
              <p className="text-sm mb-7 text-muted-foreground">
                No account, no upload to a server — the simulation runs in your browser.
              </p>
              <Button asChild size="lg" className="font-medium group">
                <Link href="/forecast">
                  Open the forecaster{" "}
                  <ArrowRight size={15} className="transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>
            </div>
          </div>
        </Reveal>
      </section>

      <Footer />
    </div>
  );
}
