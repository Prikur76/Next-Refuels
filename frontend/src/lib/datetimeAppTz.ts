/**
 * Дата/время заправок: календарные значения в часовом поясе приложения
 * (как на сервере TIME_ZONE), без привязки к локали браузера.
 */

const PART_TYPES = [
  "year",
  "month",
  "day",
  "hour",
  "minute",
] as const;

/**
 * Мгновение (ISO из API) → значение для input[type=datetime-local]
 * в заданном IANA-поясе.
 */
export function instantIsoToDatetimeLocalInZone(
  iso: string,
  ianaZone: string,
): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return "";
  }
  try {
    const fmt = new Intl.DateTimeFormat("en-CA", {
      timeZone: ianaZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    const parts = fmt.formatToParts(d);
    const get = (type: (typeof PART_TYPES)[number]) =>
      parts.find((p) => p.type === type)?.value ?? "";
    const y = get("year");
    const m = get("month");
    const day = get("day");
    let h = get("hour");
    let min = get("minute");
    if (/^\d$/.test(h)) {
      h = `0${h}`;
    }
    if (/^\d$/.test(min)) {
      min = `0${min}`;
    }
    if (!y || !m || !day || !h || !min) {
      return "";
    }
    return `${y}-${m}-${day}T${h}:${min}`;
  } catch {
    return "";
  }
}

/**
 * Значение datetime-local (календарное время в поясе приложения) → строка
 * для PATCH: без суффикса Z, сервер интерпретирует как наивное время в
 * settings.TIME_ZONE.
 */
export function normalizeWallDatetimeForApi(localValue: string): string {
  const trimmed = localValue.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.length === 16 && trimmed[13] === "T") {
    return `${trimmed}:00`;
  }
  return trimmed;
}
