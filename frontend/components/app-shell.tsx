import { CircleCheckBig, Clock3, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/review" aria-label="CHRONOS review home">
          <span className="brand-mark" aria-hidden="true">
            <Clock3 size={19} strokeWidth={2.2} />
          </span>
          <span>
            <strong>CHRONOS</strong>
            <small>Change Intelligence</small>
          </span>
        </a>
        <nav aria-label="Primary navigation">
          <a className="nav-link active" href="/review" aria-current="page">
            Review
          </a>
        </nav>
        <div className="certified-chip">
          <ShieldCheck size={15} aria-hidden="true" />
          Certified source
          <CircleCheckBig size={13} aria-hidden="true" />
        </div>
      </header>
      {children}
    </div>
  );
}
