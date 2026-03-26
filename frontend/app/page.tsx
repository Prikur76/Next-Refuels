"use client";

import { useMemo } from "react";
import Link from "next/link";

import { useMeQuery } from "@/components/auth/useMe";

export default function HomePage() {
  const meQuery = useMeQuery({ enabled: true });
  const groups = meQuery.data?.groups ?? [];

  const links = useMemo(() => {
    const isAdmin = groups.includes("Администратор");
    const isManager = groups.includes("Менеджер");
    const isFueler = groups.includes("Заправщик");

    const items: Array<{
      key: string;
      href: string;
      label: string;
      className?: string;
    }> = [
      {
        key: "fuel-add",
        href: "/fuel/add",
        label: "Новая заправка",
        className: "btn-app btn-primary block",
      },
    ];

    if (isManager || isAdmin) {
      items.push({
        key: "analytics",
        href: "/analytics",
        label: "Аналитика",
        className: "btn-app block",
      });
    }

    if (isManager || isAdmin || isFueler) {
      items.push({
        key: "access",
        href: "/access",
        label: "Доступ",
        className: "btn-app block",
      });
    }

    return items;
  }, [groups]);

  return (
    <div className="page-wrap">
      <div className="card p-4">
        <h1 className="text-xl font-bold">Next-Refuels</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Быстрый доступ к ключевым разделам.
        </p>

        <div className="home-grid mt-4">
          {links.map((link) => (
            <Link key={link.key} href={link.href} className={link.className}>
              {link.label}
            </Link>
          ))}
        </div>

        <div className="mt-4 text-xs text-[var(--muted)]">
          Примечание: доступ контролируется группами Django.
        </div>
      </div>
    </div>
  );
}

