import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaaS Platform — Ship Faster",
  description:
    "Your on-demand creative and engineering partner. Submit tasks, track progress, and receive polished deliverables.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface antialiased">{children}</body>
    </html>
  );
}
