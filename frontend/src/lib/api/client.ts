"use client";

import { ApiError } from "./errors";

const API_PUBLIC_BASE_URL = process.env.NEXT_PUBLIC_API_URL;
const API_INTERNAL_BASE_URL = process.env.NEXT_INTERNAL_API_URL;
const LOGIN_PAGE_PATH = "/login";

function requireApiBaseUrl(): string {
  const rawBaseUrl =
    typeof window === "undefined" ? API_INTERNAL_BASE_URL ?? API_PUBLIC_BASE_URL : API_PUBLIC_BASE_URL;

  if (rawBaseUrl === undefined) {
    throw new Error(
      "NEXT_PUBLIC_API_URL не задан. Укажите переменную окружения."
    );
  }
  return rawBaseUrl.replace(/\/+$/, "");
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
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
  return null;
}

function getCsrfToken(): string | null {
  return getCookie("csrftoken");
}

let csrfBootstrapPromise: Promise<void> | null = null;

async function ensureCsrfCookie(baseUrl: string): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }
  if (getCsrfToken()) {
    return;
  }
  if (!csrfBootstrapPromise) {
    csrfBootstrapPromise = fetch(`${baseUrl}/api/v1/auth/csrf`, {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    })
      .then(() => undefined)
      .finally(() => {
        csrfBootstrapPromise = null;
      });
  }
  await csrfBootstrapPromise;
}

function resolvedClientTimezoneHeader(): Record<string, string> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz) {
      return { "X-Client-Timezone": tz };
    }
  } catch {
    // Ignore: недоступно в среде без Intl.
  }
  return {};
}

export async function apiFetchJson<TResponse>(
  path: string,
  init?: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
    clientTimezone?: boolean;
  }
): Promise<TResponse> {
  const baseUrl = requireApiBaseUrl();
  const url = `${baseUrl}${path.startsWith("/") ? "" : "/"}${path}`;

  const method = init?.method ?? "GET";
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.clientTimezone ? resolvedClientTimezoneHeader() : {}),
    ...(init?.headers ?? {}),
  };

  const isUnsafe =
    method !== "GET" &&
    method !== "HEAD" &&
    method !== "OPTIONS";

  if (isUnsafe) {
    await ensureCsrfCookie(baseUrl);
  }
  const csrfToken = isUnsafe ? getCsrfToken() : null;
  if (isUnsafe && csrfToken && !headers["X-CSRFToken"]) {
    headers["X-CSRFToken"] = csrfToken;
  }

  let body: BodyInit | undefined;
  if (init?.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body);
  }

  const response = await fetch(url, {
    method,
    credentials: "include",
    headers,
    body,
    signal: init?.signal,
  });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      const currentPath = window.location.pathname;
      if (
        !currentPath.startsWith("/login") &&
        !currentPath.startsWith("/accounts/login")
      ) {
        window.location.replace(LOGIN_PAGE_PATH);
      }
    }
    throw new ApiError({
      status: 401,
      message: "Требуется авторизация",
    });
  }

  if (!response.ok) {
    const text = await response.text();
    let detail: string | undefined;
    try {
      const parsed = JSON.parse(text);
      detail = parsed?.detail ?? parsed?.message ?? undefined;
    } catch {
      detail = text || undefined;
    }
    throw new ApiError({
      status: response.status,
      detail,
      message: detail ?? `HTTP ${response.status}`,
    });
  }

  const contentType = response.headers.get("content-type");
  if (!contentType?.includes("application/json")) {
    throw new ApiError({
      status: response.status,
      message: "Ответ не является JSON",
    });
  }

  return (await response.json()) as TResponse;
}

