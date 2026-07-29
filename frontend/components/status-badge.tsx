import type { ReactNode } from "react";

type Tone = "certified" | "hold" | "unresolved" | "high" | "neutral";

export function StatusBadge({
  tone,
  children,
}: {
  tone: Tone;
  children: ReactNode;
}) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}
