"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { setupOwnPassword } from "@/lib/api/endpoints";

export default function PasswordSetupPage() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");

  const setupMutation = useMutation({
    mutationFn: setupOwnPassword,
    onSuccess: () => {
      setMessage("Пароль успешно установлен. Выполняется переход...");
      window.setTimeout(() => {
        window.location.replace("/fuel/add");
      }, 700);
    },
    onError: (err) => {
      setMessage((err as Error).message || "Не удалось сохранить пароль.");
    },
  });

  return (
    <div className="page-wrap">
      <section className="card p-4">
        <h1 className="section-title">Первый вход: настройка пароля</h1>
        <p className="section-subtitle mt-1">
          Установите собственный постоянный пароль.
        </p>

        {message ? (
          <div className="muted-box mt-3 text-sm text-[var(--muted)]">{message}</div>
        ) : null}

        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            setMessage("");
            const passwordValue = password.trim();
            const confirmValue = confirmPassword.trim();
            if (passwordValue.length < 8) {
              setMessage("Пароль должен содержать минимум 8 символов.");
              return;
            }
            if (passwordValue !== confirmValue) {
              setMessage("Пароли не совпадают.");
              return;
            }
            setupMutation.mutate({ password: passwordValue, generate: false });
          }}
        >
          <label className="label-app">
            Новый пароль
            <input
              type={showPassword ? "text" : "password"}
              className="input-app"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Минимум 8 символов"
              autoComplete="new-password"
            />
          </label>
          <label className="label-app">
            Повторите пароль
            <input
              type={showPassword ? "text" : "password"}
              className="input-app"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Повторите пароль"
              autoComplete="new-password"
            />
          </label>
          <label className="mt-1 inline-flex items-center gap-2 text-xs text-[var(--muted)]">
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(e) => setShowPassword(e.target.checked)}
            />
            Показать пароль
          </label>
          <div className="toolbar">
            <button
              type="submit"
              className="btn-app btn-primary"
              aria-disabled={setupMutation.isPending}
            >
              Сохранить мой пароль
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
