"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Droplets,
  Home,
  LogOut,
  Settings,
  Shield,
} from "lucide-react";

import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { PageTransition } from "@/components/routing/PageTransition";
import { ViewTransitionLink } from "@/components/routing/ViewTransitionLink";
import { useMeQuery } from "@/components/auth/useMe";
import { SkeletonLine } from "@/components/skeleton/Skeleton";
import { ApiError } from "@/lib/api/errors";
import type { UserMeOut } from "@/lib/api/types";

type NavItem = {
  key: string;
  href: string;
  label: string;
  icon: React.ReactNode;
  external?: boolean;
};

const SIDEBAR_COLLAPSED_STORAGE_KEY = "next_refuels.sidebar.collapsed";

function normalizeUserText(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim();
  if (!normalized) return "";
  const invalidTokens = new Set(["none", "null", "undefined", "nan"]);
  const lowered = normalized.toLowerCase();
  const parts = lowered.split(/\s+/).filter(Boolean);
  const allInvalid = parts.length > 0 && parts.every((p) => invalidTokens.has(p));
  if (invalidTokens.has(lowered) || allInvalid) {
    return "";
  }
  return normalized;
}

function UserTitle({ me }: { me: UserMeOut }) {
  const username = normalizeUserText(me.username);
  const fullName = normalizeUserText(me.full_name);
  const primary = fullName || username || "Пользователь";
  const secondary = username && username !== primary ? `@${username}` : "";

  return (
    <div>
      <div className="text-sm font-semibold">{primary}</div>
      <div className="mt-1 text-xs text-[var(--muted)]">
        {secondary || "Профиль активен"}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname.startsWith("/login");
  const isPasswordSetupPage = pathname.startsWith("/password-setup");
  const isPublicPage = isLoginPage || isPasswordSetupPage;
  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isSidebarPreferenceLoaded, setIsSidebarPreferenceLoaded] = useState(false);
  const meQuery = useMeQuery({ enabled: !isLoginPage });
  useEffect(() => {
    if (isPublicPage) {
      return;
    }
    if (meQuery.isPending) {
      return;
    }
    const isUnauthorized =
      meQuery.error instanceof ApiError && meQuery.error.status === 401;
    if (isUnauthorized || (!meQuery.data && !meQuery.isError)) {
      window.location.replace("/login");
    }
  }, [
    isPublicPage,
    meQuery.data,
    meQuery.error,
    meQuery.isError,
    meQuery.isPending,
  ]);

  useEffect(() => {
    if (!meQuery.data) {
      return;
    }
    if (meQuery.data.must_change_password && !isPasswordSetupPage) {
      window.location.replace("/password-setup");
    }
    if (!meQuery.data.must_change_password && isPasswordSetupPage) {
      window.location.replace("/fuel/add");
    }
  }, [isPasswordSetupPage, meQuery.data]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 919px)");
    const updateMobileState = () => {
      setIsMobile(mediaQuery.matches);
    };

    updateMobileState();
    mediaQuery.addEventListener("change", updateMobileState);
    return () => {
      mediaQuery.removeEventListener("change", updateMobileState);
    };
  }, []);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
      if (raw === "1") {
        setIsSidebarCollapsed(true);
      } else if (raw === "0") {
        setIsSidebarCollapsed(false);
      }
    } catch {
      // Ignore storage errors (private mode, disabled storage, etc.).
    } finally {
      setIsSidebarPreferenceLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!isSidebarPreferenceLoaded) return;
    try {
      window.localStorage.setItem(
        SIDEBAR_COLLAPSED_STORAGE_KEY,
        isSidebarCollapsed ? "1" : "0"
      );
    } catch {
      // Ignore storage errors without blocking UI.
    }
  }, [isSidebarCollapsed, isSidebarPreferenceLoaded]);

  const access = useMemo(() => {
    const groups = meQuery.data?.groups ?? [];
    const isAdmin = groups.includes("Администратор");
    const isManager = groups.includes("Менеджер");
    const isFueler = groups.includes("Заправщик");
    return {
      hasReportsAccess: isManager || isAdmin,
      hasAccessAdmin: isManager || isAdmin,
      hasAccessPage: isManager || isAdmin || isFueler,
      isManager,
      isAdmin,
      isFueler,
    };
  }, [meQuery.data?.groups]);

  const djangoAdminUrl = useMemo(() => {
    const raw = process.env.NEXT_PUBLIC_DJANGO_ADMIN_URL;
    const value = typeof raw === "string" ? raw.trim() : "";
    if (value) return value;
    return "/admin/";
  }, []);

  const navItems = useMemo<NavItem[]>(
    () => {
      const items: NavItem[] = [
        {
          key: "home",
          href: "/",
          label: "Главная",
          icon: <Home size={18} />,
        },
      ];

      if (access.hasReportsAccess) {
        items.push({
          key: "analytics",
          href: "/analytics",
          label: "Аналитика",
          icon: <BarChart3 size={18} />,
        });
      }

      items.push({
        key: "entry",
        href: "/fuel/add",
        label: "Заправка",
        icon: <Droplets size={18} />,
      });

      if (access.hasAccessPage) {
        items.push({
          key: "access",
          href: "/access",
          label: "Доступ",
          icon: <Shield size={18} />,
        });
      }

      if (access.isAdmin) {
        items.push({
          key: "django-admin",
          href: djangoAdminUrl,
          label: "Django admin",
          icon: <Settings size={18} />,
          external: true,
        });
      }

      return items;
    },
    [access.hasAccessPage, access.hasReportsAccess, access.isAdmin, djangoAdminUrl]
  );

  const activeKey = navItems
    .filter((it) => pathname.startsWith(it.href))
    .sort((a, b) => b.href.length - a.href.length)[0]?.key;

  const readCookie = (name: string): string => {
    if (typeof document === "undefined") {
      return "";
    }
    const chunks = document.cookie ? document.cookie.split(";") : [];
    for (const chunk of chunks) {
      const trimmed = chunk.trim();
      if (!trimmed) continue;
      const [key, ...rest] = trimmed.split("=");
      if (key === name) {
        return decodeURIComponent(rest.join("="));
      }
    }
    return "";
  };

  const handleLogout = (): void => {
    const csrfToken = readCookie("csrftoken");
    if (!csrfToken) {
      window.location.assign("/login");
      return;
    }

    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/accounts/logout/";
    form.style.display = "none";

    const csrfInput = document.createElement("input");
    csrfInput.type = "hidden";
    csrfInput.name = "csrfmiddlewaretoken";
    csrfInput.value = csrfToken;
    form.appendChild(csrfInput);

    const nextInput = document.createElement("input");
    nextInput.type = "hidden";
    nextInput.name = "next";
    nextInput.value = "/login";
    form.appendChild(nextInput);

    document.body.appendChild(form);
    form.submit();
  };

  if (isPublicPage) {
    return (
      <main className="content" aria-label="Основной контент">
        <div className="page-wrap">
          <PageTransition>{children}</PageTransition>
        </div>
      </main>
    );
  }

  if (meQuery.isPending || !meQuery.data) {
    return (
      <main className="content" aria-label="Основной контент">
        <div className="page-wrap">
          <div className="card p-4">
            <div className="space-y-2">
              <SkeletonLine height={16} width={180} />
              <SkeletonLine height={16} width={120} />
              <SkeletonLine height={16} width={220} />
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell">
      {!isMobile ? (
        <aside
          className={`sidebar cq-desktop ${isSidebarCollapsed ? "sidebar-collapsed" : ""}`}
          aria-label="Боковая панель"
        >
          <div className="sidebar-header">
            {!isSidebarCollapsed ? (
              <ViewTransitionLink
                href="/"
                title="Главная"
                className="min-w-0"
                aria-label="Перейти на главную"
                style={{ textDecoration: "none", color: "inherit" }}
              >
                <div className="sidebar-brand-row">
                  <Image
                    src="/logo.png"
                    alt="Next-Refuels"
                    className="sidebar-logo"
                    width={40}
                    height={40}
                  />
                  <div className="sidebar-brand-text">
                    <div className="text-sm font-bold">Next-Refuels</div>
                    <div className="mt-1 text-xs text-[var(--muted)]">
                      Навигация
                    </div>
                  </div>
                </div>
              </ViewTransitionLink>
            ) : null}
            <button
              type="button"
              className="btn-app sidebar-collapse-btn"
              aria-label={
                isSidebarCollapsed
                  ? "Развернуть боковое меню"
                  : "Свернуть боковое меню"
              }
              onClick={() => setIsSidebarCollapsed((prev) => !prev)}
            >
              {isSidebarCollapsed ? (
                <ChevronRight className="sidebar-collapse-icon" aria-hidden="true" />
              ) : (
                <ChevronLeft className="sidebar-collapse-icon" aria-hidden="true" />
              )}
            </button>
          </div>

          <div className="sidebar-nav">
            {navItems.map((item) => {
              const isActive = item.key === activeKey;
              const ariaCurrent = isActive ? ("page" as const) : undefined;
              const commonProps = {
                title: isSidebarCollapsed ? item.label : undefined,
                className: `sidebar-nav-item no-select-tap ${
                  isActive ? "sidebar-nav-item-active" : ""
                } ${isSidebarCollapsed ? "sidebar-nav-item-collapsed" : ""}`,
              };

              if (item.external) {
                const isDjangoAdmin = item.key === "django-admin";
                return (
                  <a
                    key={item.key}
                    {...commonProps}
                    href={item.href}
                    target={isDjangoAdmin ? "_blank" : "_self"}
                    rel={isDjangoAdmin ? "noopener noreferrer" : "noreferrer"}
                    onClick={(e) => {
                      if (!isDjangoAdmin) return;
                      e.preventDefault();
                      if (typeof window === "undefined") return;
                      window.open(item.href, "_blank", "noopener,noreferrer");
                    }}
                    aria-current={ariaCurrent}
                  >
                    <span aria-hidden="true">{item.icon}</span>
                    {!isSidebarCollapsed ? (
                      <span>{item.label}</span>
                    ) : null}
                  </a>
                );
              }

              return (
                <ViewTransitionLink
                  key={item.key}
                  {...commonProps}
                  href={item.href}
                  aria-current={ariaCurrent}
                >
                  <span aria-hidden="true">{item.icon}</span>
                  {!isSidebarCollapsed ? <span>{item.label}</span> : null}
                </ViewTransitionLink>
              );
            })}
          </div>

          <div className="sidebar-footer">
            <div className="sidebar-user card">
              {meQuery.isPending ? (
                <div className="space-y-2">
                  <SkeletonLine height={12} width={120} />
                  <SkeletonLine height={12} width={90} />
                </div>
              ) : meQuery.data ? (
                <UserTitle me={meQuery.data} />
              ) : (
                <div className="text-xs text-[var(--muted)]">Нет данных пользователя</div>
              )}
            </div>
            <div className="sidebar-actions">
              <button
                type="button"
                className="btn-app no-select-tap sidebar-logout-btn"
                title={isSidebarCollapsed ? "Выйти" : undefined}
                onClick={handleLogout}
              >
                <span className="inline-flex items-center gap-2">
                  <LogOut size={16} aria-hidden="true" />
                  {!isSidebarCollapsed ? <span>Выйти</span> : null}
                </span>
              </button>
              <ThemeToggle />
            </div>
          </div>
        </aside>
      ) : null}

      <main className="content" aria-label="Основной контент">
        <div className="page-wrap">
          <header className="card p-4">
            <div className="text-sm font-bold">Next-Refuels</div>
            <div className="mt-1 text-xs text-[var(--muted)]">
              Ввод и отчеты по заправкам
            </div>
          </header>

          <div className="mt-4">
            <PageTransition>{children}</PageTransition>
          </div>
        </div>
      </main>

      <nav className="tabbar cq-mobile" aria-label="Нижняя навигация">
        <div className="tabbar-inner">
          {navItems.map((item) => {
            const isActive = item.key === activeKey;

            if (item.key === "home" || item.key === "django-admin") {
              return null;
            }

            if (item.external) {
              const isDjangoAdmin = item.key === "django-admin";
              return (
                <a
                  key={item.key}
                  href={item.href}
                  className="tabbar-item no-select-tap"
                  target={isDjangoAdmin ? "_blank" : "_self"}
                  rel={
                    isDjangoAdmin
                      ? "noopener noreferrer"
                      : "noreferrer"
                  }
                  aria-current={isActive ? "page" : undefined}
                >
                  {item.icon}
                  <span className="text-xs">{item.label}</span>
                </a>
              );
            }

            return (
              <ViewTransitionLink
                key={item.key}
                href={item.href}
                className="tabbar-item no-select-tap"
                aria-current={isActive ? "page" : undefined}
              >
                {item.icon}
                <span className="text-xs">{item.label}</span>
              </ViewTransitionLink>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

