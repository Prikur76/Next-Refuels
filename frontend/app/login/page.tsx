"use client";

import { useEffect, useState } from "react";
import { Lock, ShieldCheck, Sparkles } from "lucide-react";

function getCookie(name: string): string {
  if (typeof document === "undefined") {
    return "";
  }
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const trimmed = cookie.trim();
    if (!trimmed) continue;
    const [key, ...rest] = trimmed.split("=");
    if (key === name) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return "";
}

export default function LoginPage() {
  const [csrfToken, setCsrfToken] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [csrfReady, setCsrfReady] = useState(false);
  const [username, setUsername] = useState("");
  const [errorText, setErrorText] = useState("");
  const [nextPath, setNextPath] = useState("/");

  useEffect(() => {
    let isActive = true;

    async function bootstrapCsrf(): Promise<void> {
      try {
        await fetch("/api/v1/auth/csrf", {
          method: "GET",
          credentials: "include",
          headers: { Accept: "application/json" },
        });
      } catch {
        // Graceful fallback: Django login page may still set token.
      }

      if (!isActive) {
        return;
      }
      setCsrfToken(getCookie("csrftoken"));
      setCsrfReady(true);
    }

    bootstrapCsrf();
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const error = params.get("error") || "";
    const usernameParam = params.get("username") || "";
    const nextParam = params.get("next") || "/";

    if (error === "invalid_credentials") {
      setErrorText("Проверьте логин и пароль.");
    } else {
      setErrorText("");
    }

    setUsername(usernameParam);
    setNextPath(nextParam.startsWith("/") ? nextParam : "/");
  }, []);

  return (
    <div className="page-wrap login-page-wrap">
      <section className="relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface-1)] shadow-[var(--shadow-soft)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(80% 80% at 8% 8%, color-mix(in srgb, var(--primary) 16%, transparent) 0%, transparent 60%), radial-gradient(70% 70% at 92% 12%, color-mix(in srgb, var(--primary) 12%, transparent) 0%, transparent 55%)",
          }}
        />

        <div className="relative grid grid-cols-1 gap-0 md:grid-cols-[1.1fr_1fr]">
          <div className="border-b border-[var(--border)] p-6 md:border-b-0 md:border-r md:p-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--muted)]">
              <Sparkles size={14} aria-hidden="true" />
              Корпоративный доступ Next-Refuels
            </div>

            <h1 className="mt-4 text-2xl font-semibold tracking-tight md:text-3xl">
              Добро пожаловать
            </h1>
            <p className="mt-3 max-w-xl text-sm text-[var(--muted)] md:text-base">
              Войдите в систему, чтобы работать с вводом заправок, отчетами и
              управлением доступом.
            </p>

            <ul className="mt-6 space-y-3">
              <li className="flex items-start gap-3 text-sm">
                <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)]">
                  <ShieldCheck size={15} aria-hidden="true" />
                </span>
                <span>
                  Безопасная сессия и контроль прав доступа по ролям
                </span>
              </li>
              <li className="flex items-start gap-3 text-sm">
                <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)]">
                  <Lock size={15} aria-hidden="true" />
                </span>
                <span>
                  Доступ к данным только для авторизованных пользователей
                </span>
              </li>
            </ul>
          </div>

          <div className="p-6 md:p-8">
            <div className="card p-5">
              <h2 className="text-base font-semibold">Вход в аккаунт</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Используйте корпоративный логин и пароль.
              </p>

              <form
                method="post"
                action="/accounts/login/"
                className="mt-5"
              >
                <input
                  type="hidden"
                  name="csrfmiddlewaretoken"
                  value={csrfToken}
                />
                <input type="hidden" name="next" value={nextPath} />

                {errorText ? (
                  <div className="mb-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {errorText}
                  </div>
                ) : null}

                <label className="label-app">
                  Логин
                  <input
                    type="text"
                    name="username"
                    className="input-app"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </label>

                <label className="label-app mt-3">
                  Пароль
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    className="input-app"
                    autoComplete="current-password"
                    required
                  />
                </label>

                <label className="mt-2 inline-flex items-center gap-2 text-xs text-[var(--muted)]">
                  <input
                    type="checkbox"
                    checked={showPassword}
                    onChange={(e) => setShowPassword(e.target.checked)}
                  />
                  Показать пароль
                </label>

                <button
                  type="submit"
                  className="btn-app btn-primary mt-4 inline-flex w-full items-center justify-center"
                  disabled={!csrfReady}
                >
                  {csrfReady ? "Войти" : "Подготовка..."}
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

