import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Radio, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Header() {
  const [open, setOpen] = useState(false);
  const [location] = useLocation();

  const scrollToSection = (id: string) => {
    setOpen(false);
    if (location !== "/") return; // section anchors only exist on Home
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/85 backdrop-blur-md">
      <div className="container max-w-6xl mx-auto flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-gradient-to-br from-primary to-secondary">
            <Radio size={16} className="text-background" strokeWidth={2.5} />
          </span>
          <span className="text-lg font-medium tracking-tight text-foreground">CausalCast</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground transition-colors">Product</Link>
          <button onClick={() => scrollToSection("method")} className="hover:text-foreground transition-colors">
            Method
          </button>
          <button onClick={() => scrollToSection("trust")} className="hover:text-foreground transition-colors">
            Trust
          </button>
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Button asChild size="sm" className="font-medium">
            <Link href="/forecast">Open Forecaster</Link>
          </Button>
        </div>

        <button className="md:hidden text-foreground" onClick={() => setOpen(!open)} aria-label="Toggle menu">
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden container max-w-6xl mx-auto pb-4 flex flex-col gap-3 text-muted-foreground">
          <Link href="/" className="py-1" onClick={() => setOpen(false)}>Home</Link>
          <button className="py-1 text-left" onClick={() => scrollToSection("method")}>Method</button>
          <button className="py-1 text-left" onClick={() => scrollToSection("trust")}>Trust</button>
          <Button asChild size="sm" className="font-medium mt-1 w-fit">
            <Link href="/forecast">Open Forecaster</Link>
          </Button>
        </div>
      )}
    </header>
  );
}
