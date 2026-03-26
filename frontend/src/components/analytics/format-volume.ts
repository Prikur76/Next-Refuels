import { formatDecimalRu } from "@/lib/format-number-ru";

export function formatVolumeLiters(
  value: number | string | null | undefined,
): string {
  return formatDecimalRu(value);
}
