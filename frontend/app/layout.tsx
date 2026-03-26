import "./globals.css";

import type { Metadata } from "next";

import { AppProviders } from "@/components/AppProviders";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Next-Refuels",
  description: "Учет заправок автопарка",
};

function ThemeInitScript() {
  const script = `
    (function () {
      try {
        var saved = localStorage.getItem("next_refuels:theme");
        var theme = saved;
        if (!theme) {
          theme = window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
        }
        document.documentElement.dataset.theme = theme;
      } catch (e) {}
    })();
  `;

  return (
    <script
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: script }}
    />
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="color-scheme" content="light dark" />
        <link
          rel="icon"
          href="/favicon.png"
          type="image/png"
          sizes="any"
        />
        <link
          rel="apple-touch-icon"
          href="/apple-touch-icon.png"
          type="image/png"
        />
        <ThemeInitScript />
      </head>
      <body suppressHydrationWarning>
        <div className="app-cq-root">
          <AppProviders>
            <AppShell>{children}</AppShell>
          </AppProviders>
        </div>
      </body>
    </html>
  );
}

