/**
 * Форматирование чисел для графиков и таблиц (ru-RU, разделители тысяч).
 */

function toFiniteNumber(value: number | string | null | undefined): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(",", ".").trim());
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

const decimal2 = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const integerGrouped = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 0,
});

export function formatDecimalRu(
  value: number | string | null | undefined,
): string {
  return decimal2.format(toFiniteNumber(value));
}

export function formatIntegerRu(
  value: number | string | null | undefined,
): string {
  return integerGrouped.format(Math.round(toFiniteNumber(value)));
}
