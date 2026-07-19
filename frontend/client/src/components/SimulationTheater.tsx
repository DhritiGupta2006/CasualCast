import { useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ */
/* A living "video" of the product's core mechanic: hundreds of Monte */
/* Carlo revenue paths continuously simulated and streamed across a   */
/* canvas, the way a trading terminal or weather model visualizes     */
/* ensembles. No stock footage needed — the simulation itself is the  */
/* moving picture. Pauses automatically if the tab is hidden or the   */
/* user prefers reduced motion.                                      */
/* ------------------------------------------------------------------ */

type Path = {
  points: number[];
  hue: "up" | "mid" | "down";
  speed: number;
  offset: number;
  born: number;
};

function makePath(width: number, height: number, hue: Path["hue"]): Path {
  const n = 90;
  const points: number[] = [];
  let v = height * 0.55 + (Math.random() - 0.5) * height * 0.15;
  const drift = hue === "up" ? 0.55 : hue === "down" ? -0.55 : 0.02;
  for (let i = 0; i < n; i++) {
    const t = i / n;
    const vol = 3 + t * 10;
    v += drift + (Math.random() - 0.5) * vol;
    v = Math.max(height * 0.08, Math.min(height * 0.92, v));
    points.push(v);
  }
  return {
    points,
    hue,
    speed: 0.15 + Math.random() * 0.15,
    offset: Math.random() * width,
    born: performance.now(),
  };
}

export default function SimulationTheater({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [running, setRunning] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    const paths: Path[] = [];

    const styles = getComputedStyle(document.documentElement);
    const colorFor = (h: Path["hue"]) =>
      h === "up"
        ? styles.getPropertyValue("--chart-3").trim() || "#F0B429"
        : h === "down"
          ? styles.getPropertyValue("--chart-2").trim() || "#6E7BFF"
          : styles.getPropertyValue("--chart-1").trim() || "#3DDC97";

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const count = 22;
    for (let i = 0; i < count; i++) {
      const hue = i % 5 === 0 ? "up" : i % 7 === 0 ? "down" : "mid";
      paths.push(makePath(width || 800, height || 260, hue));
    }

    let raf = 0;
    let lastTime = performance.now();

    function drawGrid() {
      ctx!.strokeStyle = styles.getPropertyValue("--border").trim() || "#212838";
      ctx!.globalAlpha = 0.4;
      ctx!.lineWidth = 1;
      for (let x = 0; x < width; x += 56) {
        ctx!.beginPath();
        ctx!.moveTo(x, 0);
        ctx!.lineTo(x, height);
        ctx!.stroke();
      }
      ctx!.globalAlpha = 1;
    }

    function frame(now: number) {
      const dt = Math.min(32, now - lastTime);
      lastTime = now;

      ctx!.clearRect(0, 0, width, height);
      drawGrid();

      for (const p of paths) {
        p.offset += p.speed * (dt / 16);
        const scrollX = -((p.offset % (width + 200)) - 200);

        ctx!.beginPath();
        ctx!.lineWidth = p.hue === "mid" ? 1.6 : 1.1;
        const age = Math.min(1, (now - p.born) / 900);
        ctx!.globalAlpha = (p.hue === "mid" ? 0.55 : 0.28) * age;
        ctx!.strokeStyle = colorFor(p.hue);

        const n = p.points.length;
        const step = (width * 1.6) / n;
        for (let i = 0; i < n; i++) {
          const x = scrollX + i * step;
          if (x < -20 || x > width + 20) continue;
          const y = p.points[i];
          if (i === 0) ctx!.moveTo(x, y);
          else ctx!.lineTo(x, y);
        }
        ctx!.stroke();

        // recycle paths that have fully scrolled off, with a fresh simulation
        if (p.offset > width + 200 + n * step) {
          const idx = paths.indexOf(p);
          paths[idx] = makePath(width, height, p.hue);
        }
      }
      ctx!.globalAlpha = 1;

      // "today" marker
      const markX = width * 0.22;
      ctx!.strokeStyle = styles.getPropertyValue("--muted-foreground").trim() || "#8A93A6";
      ctx!.globalAlpha = 0.5;
      ctx!.setLineDash([3, 4]);
      ctx!.beginPath();
      ctx!.moveTo(markX, 0);
      ctx!.lineTo(markX, height);
      ctx!.stroke();
      ctx!.setLineDash([]);
      ctx!.globalAlpha = 1;

      raf = requestAnimationFrame(frame);
    }

    if (!reduceMotion) {
      raf = requestAnimationFrame(frame);
    } else {
      // Draw one static frame so reduced-motion users still see the visual.
      drawGrid();
      for (const p of paths) {
        ctx!.beginPath();
        ctx!.strokeStyle = colorFor(p.hue);
        ctx!.globalAlpha = p.hue === "mid" ? 0.55 : 0.28;
        const n = p.points.length;
        const step = (width * 1.6) / n;
        p.points.forEach((y, i) => {
          const x = i * step - 200;
          if (i === 0) ctx!.moveTo(x, y);
          else ctx!.lineTo(x, y);
        });
        ctx!.stroke();
      }
      ctx!.globalAlpha = 1;
    }

    function onVisibility() {
      if (document.hidden) {
        cancelAnimationFrame(raf);
        setRunning(false);
      } else if (!reduceMotion) {
        lastTime = performance.now();
        raf = requestAnimationFrame(frame);
        setRunning(true);
      }
    }
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <div className={`relative ${className}`}>
      <canvas ref={canvasRef} className="w-full h-full block" aria-hidden="true" />
      <div className="pointer-events-none absolute top-3 left-3 flex items-center gap-1.5 text-[10px] font-mono-data text-muted-foreground/80">
        <span
          className={`w-1.5 h-1.5 rounded-full bg-primary ${running ? "animate-pulse-subtle" : ""}`}
          style={{ boxShadow: running ? "0 0 6px var(--primary)" : "none" }}
        />
        {running ? "SIMULATING LIVE" : "PAUSED"}
      </div>
    </div>
  );
}
