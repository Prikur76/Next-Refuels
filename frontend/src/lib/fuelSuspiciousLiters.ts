/**
 * Порог объёма (л), выше которого заправка обычного авто (не ТЗ)
 * подсвечивается в журнале и в «Мои заправки».
 * Задаётся в .env: NEXT_PUBLIC_FUEL_SUSPICIOUS_LITERS_THRESHOLD
 */

function parseSuspiciousLitersThreshold(): number {
  const raw = process.env.NEXT_PUBLIC_FUEL_SUSPICIOUS_LITERS_THRESHOLD;
  if (raw === undefined || String(raw).trim() === "") {
    return 80;
  }
  const n = Number(String(raw).replace(",", ".").trim());
  if (!Number.isFinite(n) || n <= 0) {
    return 80;
  }
  return n;
}

export const FUEL_SUSPICIOUS_LITERS_THRESHOLD = parseSuspiciousLitersThreshold();

function litersToNumber(liters: number | string | null | undefined): number {
  if (typeof liters === "number") {
    return Number.isFinite(liters) ? liters : 0;
  }
  if (typeof liters === "string") {
    const parsed = Number(liters.replace(",", ".").trim());
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

/**
 * Заправка «на проверку»: не топливозаправщик и литры строго выше порога.
 */
export function isSuspiciousNonTankerRefuel(
  carIsFuelTanker: boolean,
  liters: number | string | null | undefined,
): boolean {
  if (carIsFuelTanker) {
    return false;
  }
  return litersToNumber(liters) > FUEL_SUSPICIOUS_LITERS_THRESHOLD;
}

/** Класс для <tr> в таблице с модификатором table-app--fuel-gap. */
export function suspiciousRefuelTableRowClass(suspicious: boolean): string {
  return suspicious ? "fuel-row--suspicious" : "";
}

/** Класс для карточки (мобильный список). */
export function suspiciousRefuelCardClass(suspicious: boolean): string {
  return suspicious ? "fuel-card--suspicious" : "";
}

export const SUSPICIOUS_REFUEL_ROW_TITLE =
  "Объём топлива выше порога для обычного автомобиля — проверьте запись";
