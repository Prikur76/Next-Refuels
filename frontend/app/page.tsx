"use client";

import { useMemo } from "react";
import Link from "next/link";

import { useMeQuery } from "@/components/auth/useMe";

function HomeTileIcon({
  kind,
}: {
  kind: "fuel" | "mine" | "analytics" | "access" | "bot";
}) {
  if (kind === "mine") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M9 5.75h7.25a2 2 0 0 1 2 2v10.5a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V7.75a2 2 0 0 1 2-2Z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path
          d="M9.25 9.25h5.5M9.25 12h5.5M9.25 14.75h3.5"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="m7.25 7 .65-.8c.25-.3.63-.5 1.02-.5h.92"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    );
  }

  if (kind === "fuel") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M8 4.75h7.5A1.75 1.75 0 0 1 17.25 6.5v10.75A1.75 1.75 0 0 1 15.5 19h-8A1.75 1.75 0 0 1 5.75 17.25V7.5l2.25-2.75Z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M9.25 9.5h4.5M9.25 12.5h3.25"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="m17.25 8.25 1.6 1.2c.25.18.4.47.4.77v3.03a1.5 1.5 0 0 1-3 0V11"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  if (kind === "analytics") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M5.75 18.25h12.5"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="M8.25 15.25v-4m3.75 4v-7m3.75 7v-2.5"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
        />
        <path
          d="m7.25 8.75 3-2.5 2.25 1.75 4-3"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  if (kind === "bot") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M9.5 8.75a3.25 3.25 0 0 1 4.6 0l.9.9a3.25 3.25 0 0 1 0 4.6l-1.6 1.6"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M14.5 15.25a3.25 3.25 0 0 1-4.6 0l-.9-.9a3.25 3.25 0 0 1 0-4.6l1.6-1.6"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 4.75 6.75 7v4.6c0 3.15 1.86 5.87 4.73 6.94L12 18.75l.52-.21c2.87-1.07 4.73-3.79 4.73-6.94V7L12 4.75Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m9.75 11.75 1.5 1.5 3-3"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function HomePage() {
  const meQuery = useMeQuery({ enabled: true });

  const links = useMemo(() => {
    const groups = meQuery.data?.groups ?? [];
    const isAdmin = groups.includes("Администратор");
    const isManager = groups.includes("Менеджер");
    const isFueler = groups.includes("Заправщик");

    const items: Array<{
      key: string;
      href: string;
      label: string;
      hint: string;
      tone: "brand" | "violet" | "teal";
      icon: "fuel" | "mine" | "analytics" | "access" | "bot";
      size: "regular" | "wide";
    }> = [
      {
        key: "fuel-add",
        href: "/fuel/add",
        label: "Новая заправка",
        hint: "Создать запись",
        tone: "brand",
        icon: "fuel",
        size: "wide",
      },
    ];

    if (
      (isFueler || isManager || isAdmin) &&
      meQuery.data?.has_my_editable_fuel_records
    ) {
      items.push({
        key: "fuel-mine",
        href: "/fuel/mine",
        label: "Мои заправки",
        hint: "Правка за 24 часа",
        tone: "brand",
        icon: "mine",
        size: "regular",
      });
    }

    if (isManager || isAdmin) {
      items.push({
        key: "analytics",
        href: "/analytics",
        label: "Аналитика",
        hint: "Отчеты и метрики",
        tone: "violet",
        icon: "analytics",
        size: "regular",
      });
    }

    if (isManager || isAdmin) {
      items.push({
        key: "access",
        href: "/access",
        label: "Доступ",
        hint: "Права и роли",
        tone: "teal",
        icon: "access",
        size: "regular",
      });
    }

    if ((isManager || isAdmin || isFueler) && !meQuery.data?.telegram_linked) {
      items.push({
        key: "bot-link",
        href: "/bot",
        label: "Бот",
        hint: "Привязка Telegram",
        tone: "teal",
        icon: "bot",
        size: "regular",
      });
    }

    return items;
  }, [
    meQuery.data?.groups,
    meQuery.data?.has_my_editable_fuel_records,
    meQuery.data?.telegram_linked,
  ]);

  return (
    <div className="page-wrap">
      <div className="card p-4">
        <h1 className="text-xl font-bold">Next-Refuels</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Быстрый доступ к ключевым разделам.
        </p>

        <div className="home-grid mt-4">
          {links.map((link) => (
            <Link
              key={link.key}
              href={link.href}
              className={`home-tile home-tile-${link.tone} ${
                link.size === "wide" ? "home-tile-wide" : ""
              }`}
            >
              <span className="home-tile-icon" aria-hidden="true">
                <HomeTileIcon kind={link.icon} />
              </span>
              <span className="home-tile-body">
                <span className="home-tile-title">{link.label}</span>
                <span className="home-tile-hint">{link.hint}</span>
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

