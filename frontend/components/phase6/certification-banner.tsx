import { AlertTriangle, BadgeCheck, ShieldX } from "lucide-react";

import type { AnalysisDetail, AnalysisIndex } from "@/lib/phase6-contract";

type Certification = AnalysisDetail["certification"] | AnalysisIndex["certification"];

export function CertificationBanner({ certification }: { certification: Certification }) {
  const rejected = certification.state === "PHASE_6_NOT_CERTIFIED";
  const limited = certification.state === "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS";
  const Icon = rejected ? ShieldX : limited ? AlertTriangle : BadgeCheck;
  const label = rejected
    ? "NOT CERTIFIED"
    : limited
      ? "CERTIFIED WITH NON-BLOCKING LIMITATIONS"
      : "CERTIFIED";
  return (
    <section className={`p6-certification ${rejected ? "rejected" : limited ? "limited" : "certified"}`} aria-label={`Certification state: ${label}`}>
      <Icon size={22} aria-hidden="true" />
      <div>
        <strong>{label}</strong>
        {limited && (
          <p>Live DataHub integration tests were not rerun in this offline certification environment. Static, deterministic, and frozen-fixture evidence passed.</p>
        )}
        {rejected && <p>CERTIFIED ANALYSIS UNAVAILABLE</p>}
      </div>
    </section>
  );
}
