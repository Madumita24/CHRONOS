import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@/app/globals.css";
import "@/app/phase6.css";
import "@/app/phase6-path.css";
import "@xyflow/react/dist/style.css";

export const metadata: Metadata = {
  title: "CHRONOS · Certified Change Review",
  description:
    "A read-only engineering review surface for certified CHRONOS impact analysis.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
