"use client";

import { useMemo, useState } from "react";
import type { ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import { motion } from "framer-motion";
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FileSpreadsheet } from "lucide-react";

import {
  AnalyticsByCarChart,
  AnalyticsByEmployeeChart,
} from "@/components/analytics/AnalyticsBreakdownCharts";
import { MeasureWidth } from "@/components/analytics/MeasureWidth";
import { SkeletonLine } from "@/components/skeleton/Skeleton";
import { ResponsiveSelect } from "@/components/select/ResponsiveSelect";
import { useMediaQueryMinWidth } from "@/hooks/useMediaQueryMinWidth";
import { apiFetchJson } from "@/lib/api/client";
import { getAccessRegions } from "@/lib/api/endpoints";
import type { FuelSource, FuelType, RegionOut } from "@/lib/api/types";
import { FuelReportsClientPage } from "@/features/reports/FuelReportsClientPage";
import {
  formatDecimalRu,
  formatIntegerRu,
} from "@/lib/format-number-ru";

const LINE_CHART_HEIGHT_NARROW_PX = 210;
const LINE_CHART_HEIGHT_WIDE_PX = 260;
const PIE_MAX_PX = 280;
const PIE_MIN_PX = 148;

type AnalyticsDatePresetId =
  | "today"
  | "yesterday"
  | "last7"
  | "last30"
  | "monthToDate";

const ANALYTICS_DATE_PRESETS: readonly {
  id: AnalyticsDatePresetId;
  label: string;
}[] = [
  { id: "today", label: "Сегодня" },
  { id: "yesterday", label: "Вчера" },
  { id: "last7", label: "7 дней" },
  { id: "last30", label: "30 дней" },
  { id: "monthToDate", label: "Месяц" },
] as const;

function localYmdToIso(y: number, monthIndex: number, day: number): string {
  const m = String(monthIndex + 1).padStart(2, "0");
  const d = String(day).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function todayIso(): string {
  const now = new Date();
  return localYmdToIso(now.getFullYear(), now.getMonth(), now.getDate());
}

function rangeForAnalyticsPreset(
  preset: AnalyticsDatePresetId,
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
  preset: AnalyticsDatePresetId,
  start: string,
  end: string,
): boolean {
  const r = rangeForAnalyticsPreset(preset);
  return r.start === start && r.end === end;
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
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("ru-RU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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

type AnalyticsByDayPoint = {
  date: string;
  liters: number;
};

type AnalyticsRefuelSourceSlice = {
  source: FuelSource | "";
  label: string;
  liters: number;
};

type AnalyticsRefuelChannelSlice = {
  channel: "CARD" | "TGBOT" | "TRUCK";
  label: string;
  liters: number;
  records_count: number;
};

type AnalyticsRecentRecord = {
  filled_at: string;
  employee_name: string;
  car: string;
  region_name: string | null;
  fuel_type: FuelType;
  fuel_type_label: string;
  liters: number;
};

type AnalyticsEmployeeBreakdown = {
  employee_id: number | null;
  name: string;
  liters: number;
  records_count: number;
};

type AnalyticsCarBreakdown = {
  car_id: number;
  label: string;
  state_number: string;
  model: string;
  liters: number;
  records_count: number;
};

interface AnalyticsData {
  by_day: AnalyticsByDayPoint[];
  refuel_sources: AnalyticsRefuelSourceSlice[];
  refuel_channels: AnalyticsRefuelChannelSlice[];
  recent_records: AnalyticsRecentRecord[];
  by_employee: AnalyticsEmployeeBreakdown[];
  by_car: AnalyticsCarBreakdown[];
  by_car_fuel_tankers: AnalyticsCarBreakdown[];
}

type AnalyticsViewId = "dashboard" | "journal";

function pieRadii(sizePx: number): { inner: number; outer: number } {
  return {
    inner: Math.round((60 * sizePx) / 260),
    outer: Math.round((95 * sizePx) / 260),
  };
}

function RecentTransactionMobileCard(props: {
  item: AnalyticsRecentRecord;
}): ReactElement {
  const { item } = props;
  return (
    <article className="rounded-xl border border-[var(--border)] bg-[var(--surface-0)] p-3 sm:p-4">
      <div className="mono text-xs text-[var(--muted)]">
        {formatLocalDateTime(item.filled_at)}
      </div>
      <div className="mt-3 space-y-2.5 text-sm">
        <div className="flex justify-between gap-3">
          <span className="shrink-0 text-[var(--muted)]">Сотрудник</span>
          <span className="min-w-0 text-right break-words font-medium">
            {item.employee_name}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="shrink-0 text-[var(--muted)]">Автомобиль</span>
          <span className="min-w-0 text-right break-words">{item.car}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="shrink-0 text-[var(--muted)]">Регион</span>
          <span className="min-w-0 text-right break-words">
            {item.region_name ?? "—"}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="shrink-0 text-[var(--muted)]">Топливо</span>
          <span className="min-w-0 text-right break-words">
            {item.fuel_type_label}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="shrink-0 text-[var(--muted)]">Объем</span>
          <span className="font-semibold tabular-nums">
            {formatDecimal(item.liters)} л
          </span>
        </div>
      </div>
    </article>
  );
}

export default function AnalyticsPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [startDate, setStartDate] = useState<string>(todayIso());
  const [endDate, setEndDate] = useState<string>(todayIso());
  const [regionId, setRegionId] = useState<string>("");

  const [isExportingExcel, setIsExportingExcel] = useState<boolean>(false);
  const [exportFeedback, setExportFeedback] = useState<string>("");

  const regionIdValue = useMemo<number | null>(() => {
    const trimmed = regionId.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }, [regionId]);

  const regionsQuery = useQuery<RegionOut[], Error>({
    queryKey: ["analytics", "regions"],
    queryFn: getAccessRegions,
  });

  const statsQuery = useQuery<AnalyticsData, Error>({
    queryKey: [
      "analytics",
      "stats",
      startDate,
      endDate,
      regionIdValue ?? "all",
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("start_date", startDate);
      params.set("end_date", endDate);
      if (regionIdValue !== null) {
        params.set("region_id", String(regionIdValue));
      }
      return apiFetchJson<AnalyticsData>(
        `/api/v1/analytics/stats?${params.toString()}`
      );
    },
  });

  const exportUrl = useMemo(() => {
    const params = new URLSearchParams();
    params.set("start_date", startDate);
    params.set("end_date", endDate);
    if (regionIdValue !== null) {
      params.set("region_id", String(regionIdValue));
    }
    return `/api/v1/analytics/export?${params.toString()}`;
  }, [endDate, regionIdValue, startDate]);

  const exportFileName = useMemo(() => {
    const regionPart = regionIdValue !== null ? String(regionIdValue) : "all";
    return `fuel_analytics_${sanitizeFilePart(startDate)}_${sanitizeFilePart(
      endDate
    )}_${sanitizeFilePart(regionPart)}.xlsx`;
  }, [endDate, regionIdValue, startDate]);

  async function handleExportExcel(): Promise<void> {
    setExportFeedback("");
    setIsExportingExcel(true);

    try {
      const response = await fetch(exportUrl, {
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
      link.download = exportFileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setExportFeedback("Файл сформирован и скачан.");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Не удалось скачать файл.";
      setExportFeedback(message);
    } finally {
      setIsExportingExcel(false);
    }
  }

  const activeView: AnalyticsViewId =
    searchParams.get("view") === "journal" ? "journal" : "dashboard";
  const layoutSm = useMediaQueryMinWidth(640);

  function handleViewChange(nextView: AnalyticsViewId): void {
    const params = new URLSearchParams(searchParams.toString());
    if (nextView === "dashboard") {
      params.delete("view");
    } else {
      params.set("view", "journal");
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  const viewTabs = (
    <div className="mt-3 flex flex-wrap gap-2">
      {(
        [
        { id: "dashboard", label: "Дашборд" },
        { id: "journal", label: "Журнал" },
        ] as const
      ).map((tab) => {
        const selected = activeView === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            className={
              selected
                ? "rounded-lg border border-[color-mix(in_srgb,var(--primary)_40%,var(--border))] bg-[color-mix(in_srgb,var(--primary)_14%,var(--surface-0))] px-3 py-1.5 text-xs font-semibold text-[var(--text)] transition-colors hover:border-[color-mix(in_srgb,var(--primary)_50%,var(--border))]"
                : "rounded-lg border border-[var(--border)] bg-[var(--surface-0)] px-3 py-1.5 text-xs font-medium text-[var(--text)] transition-colors hover:border-[color-mix(in_srgb,var(--primary)_25%,var(--border))]"
            }
            aria-pressed={selected}
            onClick={() => handleViewChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );

  const litersByDay = statsQuery.data?.by_day ?? [];
  const sourceSlices = statsQuery.data?.refuel_sources ?? [];
  const channelSlices = statsQuery.data?.refuel_channels ?? [];
  const recent = statsQuery.data?.recent_records ?? [];
  const byEmployee = statsQuery.data?.by_employee ?? [];
  const byCar = statsQuery.data?.by_car ?? [];
  const byCarFuelTankers = statsQuery.data?.by_car_fuel_tankers ?? [];

  const lineChartHeight = layoutSm ? LINE_CHART_HEIGHT_WIDE_PX : LINE_CHART_HEIGHT_NARROW_PX;

  const colorBySource: Record<string, string> = {
    CARD: "#8b5cf6",
    TGBOT: "#3b82f6",
    TRUCK: "#f59e0b",
    "": "#94a3b8",
  };

  const colorByRefuelChannel: Record<string, string> = {
    CARD: "#8b5cf6",
    TGBOT: "#3b82f6",
    TRUCK: "#f59e0b",
  };

  function sliceColor(source: string): string {
    return colorBySource[source] ?? "#64748b";
  }

  function channelSliceColor(channel: string): string {
    return colorByRefuelChannel[channel] ?? "#64748b";
  }

  return (
    <div className="page-wrap w-full min-w-0">
      <section className="card p-3 sm:p-4 md:p-5">
        <h1 className="section-title text-balance">Аналитика</h1>
        <p className="section-subtitle mt-1 text-pretty">
          {activeView === "journal"
            ? "Единый раздел с дашбордом и журналом записей."
            : "Объём по дням, по источникам заправки, по сотрудникам и автомобилям, последние записи."}
        </p>
        {viewTabs}
        {activeView === "journal" ? (
          <div className="mt-3 md:mt-4">
            <FuelReportsClientPage embedded />
          </div>
        ) : (
          <>
        <div className="mt-3 card p-3 sm:p-4 md:mt-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="label-app">
              С
              <input
                className="input-app"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </label>
            <label className="label-app">
              По
              <input
                className="input-app"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </label>
            <label className="label-app">
              Регион
              <ResponsiveSelect
                ariaLabel="Регион"
                value={regionId}
                onChange={(v) => setRegionId(v)}
                options={[
                  { value: "", label: "Все" },
                  ...(regionsQuery.data ?? []).map((r) => ({
                    value: String(r.id),
                    label: r.name,
                  })),
                ]}
              />
            </label>
          </div>

          <div className="mt-3">
            <div className="text-xs font-medium text-[var(--muted)]">
              Быстрый выбор периода
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {ANALYTICS_DATE_PRESETS.map((p) => {
                const active = presetMatchesRange(
                  p.id,
                  startDate,
                  endDate,
                );
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
                      const { start, end } = rangeForAnalyticsPreset(p.id);
                      setStartDate(start);
                      setEndDate(end);
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
              Нажмите кнопку для экспорта в Excel.
            </div>

            <div className="toolbar order-1 w-full sm:order-2 sm:w-auto">
              <button
                type="button"
                className="btn-app w-full min-h-11 sm:w-auto sm:min-h-0"
                aria-disabled={isExportingExcel}
                onClick={() => void handleExportExcel()}
              >
                <span className="inline-flex items-center gap-2">
                  <FileSpreadsheet size={14} aria-hidden="true" />
                  <span>{isExportingExcel ? "XLSX..." : "Экспорт в Excel"}</span>
                </span>
              </button>
            </div>
          </div>

          {exportFeedback ? (
            <div className="mt-2 text-xs text-[var(--muted)]">
              {exportFeedback}
            </div>
          ) : null}
        </div>

        <div className="mt-3 card p-3 sm:p-4 md:mt-4">
          {statsQuery.isPending ? (
            <div className="space-y-2">
              <SkeletonLine height={16} width={200} />
              <SkeletonLine height={220} width="100%" />
              <SkeletonLine height={16} width={140} />
            </div>
          ) : statsQuery.data ? (
            <>
              <div className="grid w-full min-w-0 grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
                className="card min-w-0 p-3 sm:p-4"
              >
                <div className="text-sm font-semibold">Объем по дням</div>
                <MeasureWidth
                  className="mt-3 min-w-0"
                  style={{
                    height: lineChartHeight,
                    minHeight: lineChartHeight,
                  }}
                  fallback={
                    <div
                      className="h-full w-full rounded-md bg-[color-mix(in_srgb,var(--muted)_12%,transparent)]"
                      aria-hidden="true"
                    />
                  }
                >
                  {(widthPx) => (
                    <LineChart
                      width={widthPx}
                      height={lineChartHeight}
                      data={litersByDay}
                      margin={{
                        top: 8,
                        right: layoutSm ? 10 : 4,
                        left: layoutSm ? 0 : -12,
                        bottom: layoutSm ? 8 : 36,
                      }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: layoutSm ? 12 : 10 }}
                        angle={layoutSm ? 0 : -32}
                        textAnchor={layoutSm ? "middle" : "end"}
                        height={layoutSm ? 28 : 52}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        tick={{ fontSize: layoutSm ? 12 : 10 }}
                        width={layoutSm ? undefined : 32}
                        tickFormatter={(v: number) => formatDecimal(v)}
                      />
                      <Tooltip
                        formatter={(value: unknown) =>
                          `${formatDecimal(value as number)} л`
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey="liters"
                        stroke="#22c55e"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  )}
                </MeasureWidth>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.06 }}
                className="card min-w-0 p-3 sm:p-4"
              >
                <div className="text-sm font-semibold">
                  Распределение по источникам заправки
                </div>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Объём по способу записи: только топливная карта и Telegram-бот (в
                  том числе заправки топливозаправщиков картой и ботом). Заправки
                  со способом «Топливозаправщик» (выдача топлива с бензовоза на
                  другие машины) здесь не учитываются — см. блок ниже.
                </p>
                <MeasureWidth
                  className="mt-2 w-full min-w-0"
                  style={{ minHeight: PIE_MIN_PX }}
                  fallback={
                    <div
                      className="mx-auto aspect-square w-full max-w-[280px] rounded-md bg-[color-mix(in_srgb,var(--muted)_12%,transparent)]"
                      aria-hidden="true"
                    />
                  }
                >
                  {(widthPx) => {
                    const size = Math.max(
                      PIE_MIN_PX,
                      Math.min(widthPx, PIE_MAX_PX),
                    );
                    const { inner, outer } = pieRadii(size);
                    return (
                      <div className="flex justify-center">
                        <PieChart width={size} height={size}>
                          <Tooltip
                            formatter={(value: unknown) =>
                              `${formatDecimal(value as number)} л`
                            }
                          />
                          <Pie
                            data={sourceSlices.map((s) => ({
                              name: s.label,
                              value: s.liters,
                              source: s.source,
                            }))}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={inner}
                            outerRadius={outer}
                            paddingAngle={2}
                          >
                            {sourceSlices.map((slice) => (
                              <Cell
                                key={slice.source || "_empty"}
                                fill={sliceColor(slice.source)}
                              />
                            ))}
                          </Pie>
                        </PieChart>
                      </div>
                    );
                  }}
                </MeasureWidth>

                <div className="mt-3 space-y-2">
                  {sourceSlices.map((slice) => (
                    <div
                      key={slice.source || "_empty"}
                      className="flex items-center gap-2"
                    >
                      <span
                        className="inline-block"
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: 9999,
                          background: sliceColor(slice.source),
                        }}
                      />
                      <div className="text-sm">
                        {slice.label}:{" "}
                        <span className="font-semibold">
                          {formatDecimal(slice.liters)} л
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
              </div>

              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.09 }}
                className="card mt-4 min-w-0 p-3 sm:p-4"
              >
                <div className="text-sm font-semibold">
                  Карта, Telegram-бот и топливозаправщик
                </div>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Только заправки на автомобили без отметки «топливозаправщик»:
                  карта, бот и выдача с бензовоза (способ «Топливозаправщик»).
                  Самозаправ самих топливозаправщиков здесь не учитывается.
                </p>
                {channelSlices.some((c) => c.liters > 0) ? (
                  <MeasureWidth
                    className="mt-2 w-full min-w-0"
                    style={{ minHeight: PIE_MIN_PX }}
                    fallback={
                      <div
                        className="mx-auto aspect-square w-full max-w-[280px] rounded-md bg-[color-mix(in_srgb,var(--muted)_12%,transparent)]"
                        aria-hidden="true"
                      />
                    }
                  >
                    {(widthPx) => {
                      const size = Math.max(
                        PIE_MIN_PX,
                        Math.min(widthPx, PIE_MAX_PX),
                      );
                      const { inner, outer } = pieRadii(size);
                      const pieRows = channelSlices.filter((c) => c.liters > 0);
                      return (
                        <div className="flex justify-center">
                          <PieChart width={size} height={size}>
                            <Tooltip
                              formatter={(value: unknown) =>
                                `${formatDecimal(value as number)} л`
                              }
                            />
                            <Pie
                              data={pieRows.map((c) => ({
                                name: c.label,
                                value: c.liters,
                                channel: c.channel,
                              }))}
                              dataKey="value"
                              nameKey="name"
                              innerRadius={inner}
                              outerRadius={outer}
                              paddingAngle={2}
                            >
                              {pieRows.map((c) => (
                                <Cell
                                  key={c.channel}
                                  fill={channelSliceColor(c.channel)}
                                />
                              ))}
                            </Pie>
                          </PieChart>
                        </div>
                      );
                    }}
                  </MeasureWidth>
                ) : (
                  <p className="mt-3 text-sm text-[var(--muted)]">
                    Нет записей по этим каналам за период.
                  </p>
                )}

                <div className="mt-3 space-y-2">
                  {channelSlices.map((c) => (
                    <div
                      key={c.channel}
                      className="flex flex-wrap items-baseline justify-between gap-2 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block shrink-0"
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: 9999,
                            background: channelSliceColor(c.channel),
                          }}
                        />
                        <span>{c.label}</span>
                      </div>
                      <div className="tabular-nums">
                        <span className="font-semibold">
                          {formatDecimal(c.liters)} л
                        </span>
                        <span className="text-[var(--muted)]">
                          {" "}
                          · {formatIntegerRu(c.records_count)} шт.
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            </>
          ) : (
            <div className="mt-2 text-sm text-[var(--muted)]">
              Нет данных за выбранный период.
            </div>
          )}
        </div>

        <div className="mt-3 card p-3 sm:p-4 md:mt-4">
          {statsQuery.isPending ? (
            <div className="space-y-2">
              <SkeletonLine height={16} width={220} />
              <SkeletonLine height={180} width="100%" />
              <SkeletonLine height={16} width={200} />
              <SkeletonLine height={180} width="100%" />
            </div>
          ) : statsQuery.data ? (
            <>
              <div className="grid w-full min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.04 }}
                  className="card min-w-0 p-3 sm:p-4"
                >
                  <div className="text-sm font-semibold">
                    Топ сотрудников по объёму
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Суммарный объём заправок по сотрудникам (топ до 20 за
                    период).
                  </p>
                  <AnalyticsByEmployeeChart rows={byEmployee} />
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.08 }}
                  className="card min-w-0 p-3 sm:p-4"
                >
                  <div className="text-sm font-semibold">
                    Топ автомобилей по объёму
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Без топливозаправщиков: суммарный объём по госномерам (топ
                    до 20 за период).
                  </p>
                  <AnalyticsByCarChart rows={byCar} />
                </motion.div>
              </div>
              {byCarFuelTankers.length ? (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.1 }}
                  className="card mt-4 min-w-0 p-3 sm:p-4"
                >
                  <div className="text-sm font-semibold">
                    Топливозаправщики по объёму
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Автомобили с отметкой «топливозаправщик» в справочнике (топ
                    до 20 за период). Учитываются все заправки по этим машинам,
                    включая заправку самого заправщика картой или через бота.
                  </p>
                  <AnalyticsByCarChart rows={byCarFuelTankers} />
                </motion.div>
              ) : null}
            </>
          ) : (
            <div className="text-sm text-[var(--muted)]">
              Нет данных за выбранный период.
            </div>
          )}
        </div>

        <div className="mt-3 card p-3 sm:p-4 md:mt-4">
          <div className="text-sm font-semibold">Последние транзакции</div>

          {statsQuery.isPending ? (
            <div className="mt-3 space-y-2">
              {Array.from({ length: 6 }).map((_, idx) => (
                <SkeletonLine key={idx} height={14} width="100%" />
              ))}
            </div>
          ) : recent.length ? (
            <>
              <div className="mt-3 space-y-3 lg:hidden">
                {recent.map((item, idx) => (
                  <RecentTransactionMobileCard
                    key={`${item.filled_at}-${idx}`}
                    item={item}
                  />
                ))}
              </div>
              <div className="mt-3 hidden min-w-0 overflow-x-auto lg:block">
                <table className="table-app">
                  <thead>
                    <tr>
                      <th>Дата</th>
                      <th>Сотрудник</th>
                      <th>Автомобиль</th>
                      <th>Регион</th>
                      <th>Тип топлива</th>
                      <th>Объем</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((item, idx) => (
                      <tr key={`${item.filled_at}-${idx}`}>
                        <td className="mono">
                          {formatLocalDateTime(item.filled_at)}
                        </td>
                        <td>{item.employee_name}</td>
                        <td>{item.car}</td>
                        <td>{item.region_name ?? "—"}</td>
                        <td>{item.fuel_type_label}</td>
                        <td>{formatDecimal(item.liters)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="mt-3 text-sm text-[var(--muted)]">
              Нет записей за выбранный период.
            </div>
          )}
        </div>
          </>
        )}
      </section>
    </div>
  );
}

