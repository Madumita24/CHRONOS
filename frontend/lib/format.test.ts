import { describe, expect, it } from "vitest";

import {
  compactIdentifier,
  formatCertifiedAt,
  humanize,
} from "@/lib/format";

describe("presentation formatters", () => {
  it("humanizes machine values", () => {
    expect(humanize("hold_for_review")).toBe("Hold For Review");
  });

  it("compacts long identifiers", () => {
    expect(compactIdentifier("abcdefghijklmnopqrstuvwxyz", 8)).toBe(
      "abcdefg…stuvwxyz",
    );
  });

  it("does not compact short identifiers", () => {
    expect(compactIdentifier("short", 8)).toBe("short");
  });

  it("formats certification timestamps in UTC", () => {
    expect(formatCertifiedAt("2026-07-28T23:15:35+00:00")).toContain(
      "Jul 28, 2026",
    );
  });
});
