"use client";

import { useEffect, useMemo, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, FileSpreadsheet } from "lucide-react";

import { ResponsiveSelect } from "@/components/select/ResponsiveSelect";
import {
  getAccessRegions,
  getFuelRecords,
  getReportFilters,
  getSummary,
} from "@/lib/api/endpoints";
import type {
  FuelRecordOut,
  ReportsFiltersOut,
  RecordsPageOut,
  RegionOut,
  SummaryOut,
} from "@/lib/api/types";
import { SkeletonLine } from "@/components/skeleton/Skeleton";
import { formatDecimalRu, formatIntegerRu } from "@/lib/format-number-ru";

function localYmdToIso(y: number, monthIndex: number, day: number): string {
  const m = String(monthIndex + 1).padStart(2, "0");
  const d = String(day).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function todayIso(): string {
  const now = new Date();
  return localYmdToIso(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
}

function dateOrUndefined(value: string): string | undefined {
  const v = value.trim();
  return v ? v : undefined;
}

function toNumber(value: number | string | null | undefined): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }

  if (typeof value === "string") {
    const parsed = Number(value.replace(",", ".").trim());
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function formatDecimal(value: number | string | null | undefined): string {
  return formatDecimalRu(value);
}

function formatLocalDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("ru-RU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type SortKey =
  | "id"
  | "car_state_number"
  | "liters"
  | "fuel_type"
  | "source"
  | "employee_name"
  | "region_name"
  | "filled_at";

type SortDirection = "asc" | "desc";

function sortJournalItems(
  items: FuelRecordOut[],
  sortKey: SortKey,
  sortDirection: SortDirection,
): FuelRecordOut[] {
  const direction = sortDirection === "asc" ? 1 : -1;

  return [...items].sort((left, right) => {
    if (sortKey === "id") {
      return (left.id - right.id) * direction;
    }

    if (sortKey === "liters") {
      return (toNumber(left.liters) - toNumber(right.liters)) * direction;
    }

    if (sortKey === "filled_at") {
      return (
        (new Date(left.filled_at).getTime() -
          new Date(right.filled_at).getTime()) * direction
      );
    }

    const leftValue =
      (left[sortKey] as string | number | null | undefined) ?? "";
    const rightValue =
      (right[sortKey] as string | number | null | undefined) ?? "";

    return leftValue
      .toString()
      .localeCompare(rightValue.toString(), "ru", {
        sensitivity: "base",
      }) * direction;
  });
}

const SOURCE_LABELS: Record<string, string> = {
  TGBOT: "ТГ-бот",
  CARD: "Топливная карта",
  TRUCK: "Топливозаправщик",
};

function sourceLabel(value: string): string {
  return SOURCE_LABELS[value] ?? value;
}

function fuelTankerPlateClass(isFuelTanker: boolean): string {
  return isFuelTanker
    ? "font-semibold text-amber-700 dark:text-amber-300"
    : "font-medium";
}

function renderCarPlateWithBadge(
  plate: string,
  isFuelTanker: boolean,
): ReactElement {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span>{plate}</span>
      {isFuelTanker ? (
        <span className="rounded-md border border-amber-200 bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:border-amber-700/70 dark:bg-amber-900/40 dark:text-amber-200">
          ТЗ
        </span>
      ) : null}
    </span>
  );
}

type ReportsDatePresetId = "today" | "yesterday" | "last7" | "last30" | "monthToDate";

const REPORTS_DATE_PRESETS: readonly {
  id: ReportsDatePresetId;
  label: string;
}[] = [
  { id: "today", label: "Сегодня" },
  { id: "yesterday", label: "Вчера" },
  { id: "last7", label: "7 дней" },
  { id: "last30", label: "30 дней" },
  { id: "monthToDate", label: "Месяц" },
] as const;

function rangeForReportsPreset(
  preset: ReportsDatePresetId,
): { start: string; end: string } {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  const d = now.getDate();
  const end = localYmdToIso(y, m, d);

  switch (preset) {
    case "today":
      return { start: end, end };
    case "yesterday": {
      const dt = new Date(y, m, d - 1);
      return {
        start: localYmdToIso(
          dt.getFullYear(),
          dt.getMonth(),
          dt.getDate(),
        ),
        end: localYmdToIso(
          dt.getFullYear(),
          dt.getMonth(),
          dt.getDate(),
        ),
      };
    }
    case "last7": {
      const dt = new Date(y, m, d - 6);
      return {
        start: localYmdToIso(
          dt.getFullYear(),
          dt.getMonth(),
          dt.getDate(),
        ),
        end,
      };
    }
    case "last30": {
      const dt = new Date(y, m, d - 29);
      return {
        start: localYmdToIso(
          dt.getFullYear(),
          dt.getMonth(),
          dt.getDate(),
        ),
        end,
      };
    }
    case "monthToDate":
      return { start: localYmdToIso(y, m, 1), end };
  }
}

function presetMatchesRange(
  preset: ReportsDatePresetId,
  start: string,
  end: string,
): boolean {
  const r = rangeForReportsPreset(preset);
  return r.start === start && r.end === end;
}

function sanitizeFilePart(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-zа-я0-9_-]+/gi, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function visiblePageNumbers(
  current: number,
  totalPages: number,
  siblingCount: number,
): (number | "ellipsis")[] {
  if (totalPages <= 0) {
    return [];
  }
  const windowSize = siblingCount * 2 + 1;
  if (totalPages <= windowSize + 2) {
    return Array.from({ length: totalPages }, (_, idx) => idx + 1);
  }

  const pages: (number | "ellipsis")[] = [];
  const left = Math.max(2, current - siblingCount);
  const right = Math.min(totalPages - 1, current + siblingCount);

  pages.push(1);
  if (left > 2) {
    pages.push("ellipsis");
  }
  for (let p = left; p <= right; p += 1) {
    pages.push(p);
  }
  if (right < totalPages - 1) {
    pages.push("ellipsis");
  }
  pages.push(totalPages);
  return pages;
}

function JournalPaginationBar(props: {
  currentPage: number;
  totalPages: number;
  totalRecords: number;
  offset: number;
  itemCount: number;
  hasNext: boolean;
  isBusy: boolean;
  onPageChange: (page: number) => void;
}): ReactElement {
  const {
    currentPage,
    totalPages,
    totalRecords,
    offset,
    itemCount,
    hasNext,
    isBusy,
    onPageChange,
  } = props;

  const hasPrev = currentPage > 1;
  const rangeStart =
    totalRecords === 0 || itemCount === 0 ? 0 : offset + 1;
  const rangeEnd = totalRecords === 0 ? 0 : offset + itemCount;

  const pageEntries = visiblePageNumbers(currentPage, totalPages, 1);

  return (
    <nav
      className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-3 sm:p-4"
      aria-label="Пагинация журнала"
    >
      <p className="text-center text-xs leading-relaxed text-[var(--muted)] sm:text-left sm:text-sm">
        {totalRecords === 0 ? (
          <>Нет записей за выбранный период.</>
        ) : (
          <>
            Записи{" "}
            <span className="tabular-nums font-medium text-[var(--text)]">
              {formatIntegerRu(rangeStart)}–{formatIntegerRu(rangeEnd)}
            </span>
            {" "}из{" "}
            <span className="tabular-nums font-medium text-[var(--text)]">
              {formatIntegerRu(totalRecords)}
            </span>
            {totalPages > 1 ? (
              <>
                {" "}
                <span className="text-[var(--muted)]">·</span>
                {" "}
                <span className="tabular-nums font-medium text-[var(--text)]">
                  {formatIntegerRu(currentPage)}
                </span>
                <span className="text-[var(--muted)]">/</span>
                <span className="tabular-nums font-medium text-[var(--text)]">
                  {formatIntegerRu(totalPages)}
                </span>
              </>
            ) : null}
          </>
        )}
      </p>

      {totalRecords > 0 && totalPages > 1 ? (
        <div className="mt-3 flex w-full min-w-0 justify-center">
          <div
            className="inline-flex w-full max-w-full min-w-0 items-stretch overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-0)] shadow-[var(--shadow-soft)] sm:max-w-[min(100%,42rem)]"
            role="group"
            aria-label="Переход по страницам"
          >
            <button
              type="button"
              className="inline-flex min-h-10 w-11 shrink-0 items-center justify-center border-r border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-1)_55%,var(--surface-0))] text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] active:bg-[color-mix(in_srgb,var(--muted)_12%,var(--surface-0))] disabled:pointer-events-none disabled:opacity-40 sm:w-auto sm:min-w-[5.5rem] sm:px-3"
              aria-label="Предыдущая страница"
              disabled={!hasPrev || isBusy}
              onClick={() => onPageChange(currentPage - 1)}
            >
              <ChevronLeft
                size={20}
                aria-hidden
                className="shrink-0 sm:hidden"
              />
              <span className="hidden items-center gap-1 sm:inline-flex">
                <ChevronLeft size={16} aria-hidden className="shrink-0" />
                Назад
              </span>
            </button>

            <div
              className="flex min-h-10 min-w-0 flex-1 items-center justify-center gap-0.5 overflow-x-auto overscroll-x-contain px-1 py-1 [-ms-overflow-style:none] [scrollbar-width:none] sm:gap-1 sm:px-2 [&::-webkit-scrollbar]:hidden"
              role="group"
              aria-label="Номера страниц"
            >
              {pageEntries.map((entry, idx) =>
                entry === "ellipsis" ? (
                  <span
                    key={`e-${idx}`}
                    className="inline-flex min-w-8 shrink-0 items-center justify-center px-0.5 text-xs text-[var(--muted)] sm:min-w-9 sm:text-sm"
                  >
                    …
                  </span>
                ) : (
                  <button
                    key={entry}
                    type="button"
                    className={
                      entry === currentPage
                        ? "inline-flex h-8 min-w-8 shrink-0 items-center justify-center rounded-md border border-[color-mix(in_srgb,var(--primary)_50%,var(--border))] bg-[color-mix(in_srgb,var(--primary)_14%,var(--surface-0))] px-1.5 text-xs font-semibold tabular-nums text-[var(--text)] sm:h-9 sm:min-w-9 sm:px-2 sm:text-sm"
                        : "inline-flex h-8 min-w-8 shrink-0 items-center justify-center rounded-md border border-transparent px-1.5 text-xs font-medium tabular-nums text-[var(--text)] transition-colors hover:border-[var(--border)] hover:bg-[var(--surface-2)] sm:h-9 sm:min-w-9 sm:px-2 sm:text-sm"
                    }
                    aria-label={`Страница ${entry}`}
                    aria-current={entry === currentPage ? "page" : undefined}
                    disabled={isBusy}
                    onClick={() => onPageChange(entry)}
                  >
                    {entry}
                  </button>
                ),
              )}
            </div>

            <button
              type="button"
              className="inline-flex min-h-10 w-11 shrink-0 items-center justify-center border-l border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-1)_55%,var(--surface-0))] text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] active:bg-[color-mix(in_srgb,var(--muted)_12%,var(--surface-0))] disabled:pointer-events-none disabled:opacity-40 sm:w-auto sm:min-w-[5.5rem] sm:px-3"
              aria-label="Следующая страница"
              disabled={!hasNext || isBusy}
              onClick={() => onPageChange(currentPage + 1)}
            >
              <ChevronRight
                size={20}
                aria-hidden
                className="shrink-0 sm:hidden"
              />
              <span className="hidden items-center gap-1 sm:inline-flex">
                Далее
                <ChevronRight size={16} aria-hidden className="shrink-0" />
              </span>
            </button>
          </div>
        </div>
      ) : null}
    </nav>
  );
}

export function FuelReportsClientPage({
  embedded = false,
  sharedFilters,
  onSharedFiltersChange,
}: {
  embedded?: boolean;
  sharedFilters?: {
    startDate: string;
    endDate: string;
    regionId: string;
    presetId: ReportsDatePresetId | "";
  };
  onSharedFiltersChange?: (filters: {
    startDate: string;
    endDate: string;
    regionId: string;
    presetId: ReportsDatePresetId | "";
  }) => void;
}) {
  const [fromDate, setFromDate] = useState(sharedFilters?.startDate ?? todayIso());
  const [toDate, setToDate] = useState(sharedFilters?.endDate ?? todayIso());
  const [source, setSource] = useState<string>("");
  const [employee, setEmployee] = useState<string>("");
  const [carStateNumber, setCarStateNumber] = useState<string>("");
  const [regionId, setRegionId] = useState<string>(sharedFilters?.regionId ?? "");
  const [selectedPresetId, setSelectedPresetId] = useState<
    ReportsDatePresetId | ""
  >(sharedFilters?.presetId ?? "");
  const [limit, setLimit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);
  const [queryNonce, setQueryNonce] = useState<number>(0);
  const [sortKey, setSortKey] = useState<SortKey>("filled_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [isExportingCsv, setIsExportingCsv] = useState<boolean>(false);
  const [isExportingXlsx, setIsExportingXlsx] = useState<boolean>(false);
  const [exportFeedback, setExportFeedback] = useState<string>("");

  useEffect(() => {
    if (!sharedFilters) {
      return;
    }
    setFromDate(sharedFilters.startDate);
    setToDate(sharedFilters.endDate);
    setRegionId(sharedFilters.regionId);
    setSelectedPresetId(sharedFilters.presetId);
  }, [sharedFilters]);

  useEffect(() => {
    if (!onSharedFiltersChange) {
      return;
    }
    onSharedFiltersChange({
      startDate: fromDate,
      endDate: toDate,
      regionId,
      presetId: selectedPresetId,
    });
  }, [
    toDate,
    fromDate,
    onSharedFiltersChange,
    regionId,
    selectedPresetId,
  ]);

  const regionIdValue = useMemo<number | undefined>(() => {
    const trimmed = regionId.trim();
    if (!trimmed) {
      return undefined;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : undefined;
  }, [regionId]);

  const filters = useMemo(
    () => ({
      from_date: dateOrUndefined(fromDate),
      to_date: dateOrUndefined(toDate),
      source: source || undefined,
      employee: employee.trim() || undefined,
      car_state_number: carStateNumber.trim() || undefined,
      region_id: regionIdValue,
      offset,
      limit,
    }),
    [carStateNumber, employee, fromDate, limit, offset, regionIdValue, source, toDate]
  );

  const summaryQuery = useQuery<SummaryOut, Error>({
    queryKey: ["reports", "summary", queryNonce, filters],
    queryFn: () =>
      getSummary({
        from_date: filters.from_date,
        to_date: filters.to_date,
        source: filters.source,
        employee: filters.employee,
        car_state_number: filters.car_state_number,
        region_id: filters.region_id,
      }),
    enabled: queryNonce > 0,
  });

  const optionsQuery = useQuery<ReportsFiltersOut, Error>({
    queryKey: [
      "reports",
      "filters-options",
      fromDate,
      toDate,
      source,
    ],
    queryFn: () =>
      getReportFilters({
        from_date: dateOrUndefined(fromDate),
        to_date: dateOrUndefined(toDate),
        source: source || undefined,
      }),
  });

  const regionsQuery = useQuery<RegionOut[], Error>({
    queryKey: ["reports", "regions"],
    queryFn: getAccessRegions,
  });

  const recordsQuery = useQuery<RecordsPageOut, Error>({
    queryKey: ["reports", "records", queryNonce, filters],
    queryFn: () => getFuelRecords(filters),
    enabled: queryNonce > 0,
  });

  const exportUrl = (type: "csv" | "xlsx") => {
    const params = new URLSearchParams();
    params.set("from_date", fromDate);
    params.set("to_date", toDate);
    if (source) params.set("source", source);
    if (employee.trim()) params.set("employee", employee.trim());
    if (carStateNumber.trim()) {
      params.set("car_state_number", carStateNumber.trim());
    }
    if (regionIdValue !== undefined) {
      params.set("region_id", String(regionIdValue));
    }
    return `/api/reports/export/${type}?${params.toString()}`;
  };

  const exportFileName = (type: "csv" | "xlsx"): string => {
    const parts = [fromDate, toDate];
    if (source) {
      parts.push(sourceLabel(source));
    }
    if (employee.trim()) {
      parts.push(employee.trim());
    }
    if (carStateNumber.trim()) {
      parts.push(carStateNumber.trim());
    }
    if (regionIdValue !== undefined) {
      const regionName =
        regionsQuery.data?.find((item) => item.id === regionIdValue)?.name ??
        String(regionIdValue);
      parts.push(regionName);
    }
    const suffix = parts
      .map(sanitizeFilePart)
      .filter(Boolean)
      .join("_");
    return `fuel_reports_${suffix || "export"}.${type}`;
  };

  async function handleExport(type: "csv" | "xlsx"): Promise<void> {
    const isCsv = type === "csv";
    setExportFeedback("");
    if (isCsv) {
      setIsExportingCsv(true);
    } else {
      setIsExportingXlsx(true);
    }

    try {
      const response = await fetch(exportUrl(type), {
        method: "GET",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(`Ошибка экспорта (${response.status}).`);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = exportFileName(type);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setExportFeedback("Файл сформирован и скачан.");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Не удалось скачать файл.";
      setExportFeedback(message);
    } finally {
      if (isCsv) {
        setIsExportingCsv(false);
      } else {
        setIsExportingXlsx(false);
      }
    }
  }

  const hasData = Boolean(summaryQuery.data && recordsQuery.data);

  const journalItems = recordsQuery.data?.items ?? [];
  const sortedJournalItems = sortJournalItems(
    journalItems,
    sortKey,
    sortDirection
  );

  const content = (
    <section className="card p-4">
      <h1 className="section-title">
        {embedded ? "Журнал записей" : "Отчеты"}
      </h1>
      <p className="section-subtitle mt-1">
        {embedded
          ? "Детальный журнал заправок с фильтрами и экспортом."
          : "Фильтры и журнал записей за период."}
      </p>

        <div className="mt-4 card p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <label className="label-app">
              С
              <input
                className="input-app"
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  setSelectedPresetId("");
                }}
              />
            </label>
            <label className="label-app">
              По
              <input
                className="input-app"
                type="date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value);
                  setSelectedPresetId("");
                }}
              />
            </label>
            <label className="label-app">
              Источник
              <ResponsiveSelect
                ariaLabel="Источник"
                value={source}
                onChange={(v) => setSource(v)}
                options={[
                  { value: "", label: "Все" },
                  { value: "TGBOT", label: sourceLabel("TGBOT") },
                  { value: "CARD", label: sourceLabel("CARD") },
                  { value: "TRUCK", label: sourceLabel("TRUCK") },
                ]}
              />
            </label>
            <label className="label-app">
              Сотрудник
              <ResponsiveSelect
                ariaLabel="Сотрудник"
                value={employee}
                onChange={(v) => setEmployee(v)}
                options={[
                  { value: "", label: "Все" },
                  ...(optionsQuery.data?.employees ?? []).map((name) => ({
                    value: name,
                    label: name,
                  })),
                ]}
              />
            </label>
            <label className="label-app">
              Номер машины
              <input
                className="input-app"
                type="text"
                placeholder="Напр. А123ВС"
                value={carStateNumber}
                onChange={(e) => setCarStateNumber(e.target.value)}
              />
            </label>
            <label className="label-app">
              Регион
              <ResponsiveSelect
                ariaLabel="Регион"
                value={regionId}
                onChange={(v) => {
                  setRegionId(v);
                }}
                options={[
                  { value: "", label: "Все" },
                  ...(regionsQuery.data ?? []).map((item) => ({
                    value: String(item.id),
                    label: item.name,
                  })),
                ]}
              />
            </label>
            <label className="label-app">
              Строк на страницу
              <ResponsiveSelect
                ariaLabel="Строк на страницу"
                value={String(limit)}
                onChange={(v) => {
                  const nextLimit = Number(v);
                  setLimit(nextLimit);
                  setOffset(0);
                  if (queryNonce > 0) {
                    setQueryNonce((n) => n + 1);
                  }
                }}
                options={[
                  { value: "25", label: "25" },
                  { value: "50", label: "50" },
                  { value: "100", label: "100" },
                ]}
              />
            </label>
          </div>

          <div className="mt-3">
            <div className="text-xs font-medium text-[var(--muted)]">
              Быстрый выбор периода
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {REPORTS_DATE_PRESETS.map((p) => {
                const active = presetMatchesRange(p.id, fromDate, toDate);
                return (
                  <button
                    key={p.id}
                    type="button"
                    className={
                      active
                        ? "rounded-lg border border-[color-mix(in_srgb,var(--primary)_40%,var(--border))] bg-[color-mix(in_srgb,var(--primary)_14%,var(--surface-0))] px-3 py-1.5 text-xs font-semibold text-[var(--text)] transition-colors hover:border-[color-mix(in_srgb,var(--primary)_50%,var(--border))]"
                        : "rounded-lg border border-[var(--border)] bg-[var(--surface-0)] px-3 py-1.5 text-xs font-medium text-[var(--text)] transition-colors hover:border-[color-mix(in_srgb,var(--primary)_25%,var(--border))]"
                    }
                    aria-pressed={active}
                    onClick={() => {
                      const { start, end } = rangeForReportsPreset(p.id);
                      setFromDate(start);
                      setToDate(end);
                      setSelectedPresetId(p.id);
                      setOffset(0);
                    }}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            <div className="order-2 text-xs text-[var(--muted)] sm:order-1">
              Выберите фильтры и нажмите «Обновить».
            </div>
            <div className="toolbar order-1 w-full sm:order-2 sm:w-auto">
              <button
                type="button"
                className="btn-app btn-primary w-full min-h-11 sm:w-auto sm:min-h-9 sm:!px-3 sm:!py-1.5 sm:text-sm"
                onClick={() => {
                  setOffset(0);
                  setQueryNonce((n) => n + 1);
                }}
              >
                Обновить
              </button>

              <button
                type="button"
                className="btn-app w-full min-h-11 sm:w-auto sm:min-h-9 sm:!px-3 sm:!py-1.5 sm:text-sm"
                aria-disabled={isExportingCsv}
                onClick={() => {
                  handleExport("csv");
                }}
              >
                <span className="inline-flex items-center gap-2">
                  <Download size={14} aria-hidden="true" />
                  <span>{isExportingCsv ? "CSV..." : "CSV"}</span>
                </span>
              </button>
              <button
                type="button"
                className="btn-app w-full min-h-11 sm:w-auto sm:min-h-9 sm:!px-3 sm:!py-1.5 sm:text-sm"
                aria-disabled={isExportingXlsx}
                onClick={() => {
                  handleExport("xlsx");
                }}
              >
                <span className="inline-flex items-center gap-2">
                  <FileSpreadsheet size={14} aria-hidden="true" />
                  <span>{isExportingXlsx ? "XLSX..." : "XLSX"}</span>
                </span>
              </button>
            </div>
          </div>
          {exportFeedback ? (
            <div className="mt-2 text-xs text-[var(--muted)]">{exportFeedback}</div>
          ) : null}
        </div>

        <div className="mt-4">
          {queryNonce === 0 ? null : summaryQuery.isPending ? (
            <div className="space-y-2">
              <SkeletonLine height={16} width={180} />
              <SkeletonLine height={16} width={140} />
              <SkeletonLine height={16} width={160} />
            </div>
          ) : summaryQuery.data ? (
            <div className="card p-4">
              <div
                className="grid gap-2"
                style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}
              >
                <div className="text-sm">
                  Записей:{" "}
                  <span className="font-semibold">
                    {formatIntegerRu(summaryQuery.data.total_records)}
                  </span>
                </div>
                <div className="text-sm">
                  Литров:{" "}
                  <span className="font-semibold">
                    {formatDecimal(summaryQuery.data.total_liters)}
                  </span>
                </div>
                <div className="text-sm">
                  Средний объем:{" "}
                  <span className="font-semibold">
                    {formatDecimal(summaryQuery.data.avg_liters)}
                  </span>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="mt-4 card p-4">
          <div className="text-sm font-semibold">Журнал</div>

          {queryNonce === 0 ? (
            <div className="mt-3 muted-box text-sm text-[var(--muted)]">
              Нажмите “Обновить”, чтобы загрузить данные.
            </div>
          ) : recordsQuery.isPending ? (
            <div className="mt-3 space-y-2">
              {Array.from({ length: 8 }).map((_, idx) => (
                <SkeletonLine key={idx} height={14} width="100%" />
              ))}
            </div>
          ) : recordsQuery.data?.items?.length ? (
            <div className="mt-3">
              <div className="hidden overflow-x-auto lg:block">
                <table className="table-app">
                  <thead>
                    <tr>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "id") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("id");
                            setSortDirection("asc");
                          }}
                        >
                          ID
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "car_state_number") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("car_state_number");
                            setSortDirection("asc");
                          }}
                        >
                          Авто
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "liters") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("liters");
                            setSortDirection("desc");
                          }}
                        >
                          Литры
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "fuel_type") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("fuel_type");
                            setSortDirection("asc");
                          }}
                        >
                          Тип
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "source") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("source");
                            setSortDirection("asc");
                          }}
                        >
                          Источник
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "employee_name") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("employee_name");
                            setSortDirection("asc");
                          }}
                        >
                          Сотрудник
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "region_name") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("region_name");
                            setSortDirection("asc");
                          }}
                        >
                          Регион
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => {
                            if (sortKey === "filled_at") {
                              setSortDirection((d) =>
                                d === "asc" ? "desc" : "asc"
                              );
                              return;
                            }
                            setSortKey("filled_at");
                            setSortDirection("desc");
                          }}
                        >
                          Дата
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedJournalItems.map((item) => (
                      <tr key={item.id}>
                        <td className="mono">{formatIntegerRu(item.id)}</td>
                        <td className={fuelTankerPlateClass(item.car_is_fuel_tanker)}>
                          {renderCarPlateWithBadge(
                            item.car_state_number,
                            item.car_is_fuel_tanker,
                          )}
                        </td>
                        <td>{formatDecimal(item.liters)}</td>
                        <td>
                          {item.fuel_type === "GASOLINE"
                            ? "Бензин"
                            : "Дизель"}
                        </td>
                        <td>{sourceLabel(item.source)}</td>
                        <td>{item.employee_name}</td>
                        <td>{item.region_name || "—"}</td>
                        <td className="mono">
                          {formatLocalDateTime(item.filled_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-3 space-y-2 lg:hidden">
                {sortedJournalItems.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-xl border border-[var(--border)] bg-[var(--surface-0)] p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="mono text-xs text-[var(--muted)]">
                        ID {item.id}
                      </div>
                      <div className="mono text-xs text-[var(--muted)]">
                        {formatLocalDateTime(item.filled_at)}
                      </div>
                    </div>

                    <div className="mt-3 space-y-2 text-sm">
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">Авто</span>
                        <span
                          className={`min-w-0 break-words text-right ${fuelTankerPlateClass(
                            item.car_is_fuel_tanker,
                          )}`}
                        >
                          {renderCarPlateWithBadge(
                            item.car_state_number,
                            item.car_is_fuel_tanker,
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">Объем</span>
                        <span className="font-semibold tabular-nums">
                          {formatDecimal(item.liters)} л
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Топливо
                        </span>
                        <span className="min-w-0 break-words text-right">
                          {item.fuel_type === "GASOLINE" ? "Бензин" : "Дизель"}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">Источник</span>
                        <span className="min-w-0 break-words text-right">
                          {sourceLabel(item.source)}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Сотрудник
                        </span>
                        <span className="min-w-0 break-words text-right">
                          {item.employee_name}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">Регион</span>
                        <span className="min-w-0 break-words text-right">
                          {item.region_name || "—"}
                        </span>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-2 text-sm text-[var(--muted)]">
              Нет записей за выбранный период.
            </div>
          )}

          {hasData && recordsQuery.data ? (
            <JournalPaginationBar
              currentPage={Math.floor(offset / limit) + 1}
              totalPages={Math.max(
                1,
                Math.ceil(
                  (summaryQuery.data?.total_records ??
                    recordsQuery.data.total ??
                    0) / limit,
                ),
              )}
              totalRecords={
                summaryQuery.data?.total_records ??
                  recordsQuery.data?.total ??
                  0
              }
              offset={offset}
              itemCount={sortedJournalItems.length}
              hasNext={Boolean(recordsQuery.data.has_next)}
              isBusy={recordsQuery.isFetching}
              onPageChange={(page) => {
                const totalRec =
                  summaryQuery.data?.total_records ??
                  recordsQuery.data?.total ??
                  0;
                const pages = Math.max(
                  1,
                  Math.ceil(totalRec / limit),
                );
                const safePage = Math.min(Math.max(1, page), pages);
                setOffset((safePage - 1) * limit);
                setQueryNonce((n) => n + 1);
              }}
            />
          ) : null}
        </div>

    </section>
  );

  if (embedded) {
    return content;
  }

  return <div className="page-wrap">{content}</div>;
}

