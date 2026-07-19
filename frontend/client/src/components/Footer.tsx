import { Link } from "wouter";
import { Radio } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t border-border mt-24">
      <div className="container max-w-6xl mx-auto py-12 grid sm:grid-cols-3 gap-8">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-gradient-to-br from-primary to-secondary">
              <Radio size={12} className="text-background" />
            </span>
            <span className="font-medium text-foreground">CausalCast</span>
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground max-w-xs">
            Probabilistic revenue forecasting for e-commerce marketers who need
            defensible numbers, not overconfident promises.
          </p>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider mb-3 text-muted-foreground/70 font-mono-data">
            Product
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <Link href="/forecast" className="w-fit hover:text-foreground transition-colors">Forecaster</Link>
            <Link href="/" className="w-fit hover:text-foreground transition-colors">Methodology</Link>
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider mb-3 text-muted-foreground/70 font-mono-data">
            Contact
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <span>support@causalcast.io</span>
            <span>All computation runs client-side.</span>
          </div>
        </div>
      </div>
      <div className="border-t border-border py-5 text-center text-xs text-muted-foreground/60">
        © {new Date().getFullYear()} CausalCast. Forecasts are estimates, not guarantees.
      </div>
    </footer>
  );
}
