export function humanize(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => {
      const normalized = part.toLocaleLowerCase();
      if (normalized === "pii") return "PII";
      if (normalized === "s3") return "S3";
      return part[0].toUpperCase() + part.slice(1);
    })
    .join(" ");
}

export function compactIdentifier(value: string, tail = 12): string {
  if (value.length <= tail + 8) {
    return value;
  }
  return `${value.slice(0, 7)}…${value.slice(-tail)}`;
}

export function formatCertifiedAt(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
