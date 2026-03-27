"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { useMeQuery } from "@/components/auth/useMe";
import { createTelegramLinkCode } from "@/lib/api/endpoints";
import type { TelegramLinkCodeOut } from "@/lib/api/types";

export function BotLinkClientPage() {
  const meQuery = useMeQuery();
  const [telegramLinkCode, setTelegramLinkCode] =
    useState<TelegramLinkCodeOut | null>(null);
  const [msg, setMsg] = useState<string>("");
  const [copyStatus, setCopyStatus] = useState<string>("");

  function setCopyStatusWithAutoClear(message: string): void {
    setCopyStatus(message);
    window.setTimeout(() => {
      setCopyStatus("");
    }, 4000);
  }

  const createTelegramLinkCodeMutation = useMutation({
    mutationFn: createTelegramLinkCode,
    onSuccess: (payload) => {
      setTelegramLinkCode(payload);
      setMsg("");
      setCopyStatus("");
    },
    onError: (err) => {
      setMsg((err as Error).message || "Не удалось создать код привязки.");
    },
  });

  if (meQuery.data?.telegram_linked) {
    return (
      <div className="page-wrap">
        <section className="card p-4">
          <h1 className="section-title">Бот</h1>
          <p className="section-subtitle mt-1">
            Telegram уже привязан к вашей учетной записи.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="page-wrap">
      <section className="card p-4">
        <h1 className="section-title">Бот</h1>
        <p className="section-subtitle mt-1">
          Подключите Telegram-бота к вашей учетной записи.
        </p>

        <div className="mt-4">
          {msg ? (
            <div className="muted-box text-sm text-[var(--muted)]">{msg}</div>
          ) : null}
        </div>

        <div className="toolbar mt-3">
          <button
            type="button"
            className="btn-app btn-primary"
            aria-disabled={createTelegramLinkCodeMutation.isPending}
            onClick={() => {
              createTelegramLinkCodeMutation.mutate();
            }}
          >
            {createTelegramLinkCodeMutation.isPending
              ? "Генерация..."
              : "Сгенерировать код"}
          </button>
        </div>

        {telegramLinkCode ? (
          <div className="muted-box mt-3 text-sm">
            <div>
              Код: <span className="mono">{telegramLinkCode.code}</span>
            </div>
            <div className="mt-1">
              Действителен до:{" "}
              <span className="mono">{telegramLinkCode.expires_at}</span>
            </div>
            <div className="mt-1">
              TTL: <span className="mono">{telegramLinkCode.ttl_minutes}</span>{" "}
              мин.
            </div>
            <div className="mt-1">
              Команда:{" "}
              <span className="mono">{`/start ${telegramLinkCode.code}`}</span>
            </div>
            <div className="toolbar mt-3">
              <button
                type="button"
                className="btn-app"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      `/start ${telegramLinkCode.code}`
                    );
                    setCopyStatusWithAutoClear("Команда скопирована.");
                  } catch {
                    setCopyStatusWithAutoClear(
                      "Не удалось скопировать автоматически. Скопируйте вручную."
                    );
                  }
                }}
              >
                Скопировать команду
              </button>
              {telegramLinkCode.bot_link_with_start ? (
                <a
                  className="btn-app"
                  href={telegramLinkCode.bot_link_with_start}
                  target="_blank"
                  rel="noreferrer"
                >
                  Открыть бота
                </a>
              ) : null}
              {copyStatus ? (
                <span className="text-xs text-[var(--muted)]">{copyStatus}</span>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
