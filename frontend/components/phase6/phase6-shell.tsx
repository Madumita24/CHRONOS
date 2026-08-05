import { Clock3, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function Phase6Shell({ children }: { children: ReactNode }) {
  return (
    <div className="p6-shell">
      <header className="p6-topbar">
        <Link className="p6-brand" href="/analyses" aria-label="CHRONOS analyses home">
          <Clock3 size={20} aria-hidden="true" />
          <span><strong>CHRONOS</strong><small>Certified analysis review</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          <Link href="/review">Golden review</Link>
          <Link href="/analyses" aria-current="page">Analyses</Link>
        </nav>
        <span className="p6-readonly"><ShieldCheck size={15} aria-hidden="true" /> Read-only</span>
      </header>
      {children}
    </div>
  );
}
