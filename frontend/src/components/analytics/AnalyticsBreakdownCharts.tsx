"use client";

import type { ReactElement } from "react";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

import { formatVolumeLiters } from "@/components/analytics/format-volume";
import { formatDecimalRu, formatIntegerRu } from "@/lib/format-number-ru";
import { MeasureWidth } from "@/components/analytics/MeasureWidth";
import { useMediaQueryMinWidth } from "@/hooks/useMediaQueryMinWidth";

const BAR_ROW_PX = 30;
const CHART_TOP_BOTTOM_PAD_PX = 56;

function truncateAxisLabel(value: string, maxLen: number): string {
  if (value.length <= maxLen) {
    return value;
  }
  return `${value.slice(0, maxLen - 1)}…`;
}

type BreakdownRow = {
  key: string;
  axisLabel: string;
  tooltipLabel?: string;
  liters: number;
  records_count: number;
};

function HorizontalBreakdownChart(props: {
  rows: BreakdownRow[];
  barFill: string;
}): ReactElement {
  const { rows, barFill } = props;
  const wideLayout = useMediaQueryMinWidth(640);
  const yAxisWidth = wideLayout ? 152 : 92;
  const labelMaxLen = wideLayout ? 22 : 14;
  const chartData = [...rows].sort((a, b) => b.liters - a.liters);
  const rowStep = wideLayout ? BAR_ROW_PX : 26;
  const height = Math.max(
    140,
    chartData.length * rowStep + CHART_TOP_BOTTOM_PAD_PX,
  );

  return (
    <MeasureWidth
      className="mt-3 w-full min-w-0"
      style={{ height, minHeight: height }}
      fallback={
        <div
          className="h-full w-full rounded-md bg-[color-mix(in_srgb,var(--muted)_12%,transparent)]"
          aria-hidden="true"
        />
      }
    >
      {(widthPx) => (
        <BarChart
          layout="vertical"
          width={widthPx}
          height={height}
          data={chartData}
          margin={{
            top: 8,
            right: wideLayout ? 16 : 8,
            left: 0,
            bottom: 8,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: wideLayout ? 11 : 10 }}
            tickFormatter={(v: number) => formatDecimalRu(v)}
          />
          <YAxis
            type="category"
            dataKey="axisLabel"
            width={yAxisWidth}
            tick={{ fontSize: wideLayout ? 11 : 10 }}
            interval={0}
            tickFormatter={(v: string) => truncateAxisLabel(v, labelMaxLen)}
          />
          <Tooltip
            cursor={{
              fill: "color-mix(in srgb, var(--muted) 10%, transparent)",
            }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) {
                return null;
              }
              const item = payload[0]?.payload as BreakdownRow | undefined;
              if (!item) {
                return null;
              }
              return (
                <div
                  className="rounded-md border px-2 py-1.5 text-xs shadow-md"
                  style={{
                    background: "var(--surface-1)",
                    borderColor: "var(--border)",
                    color: "var(--text)",
                  }}
                >
                  <div className="max-w-[260px] font-medium leading-snug">
                    {item.tooltipLabel ?? label}
                  </div>
                  <div className="mt-1">
                    Объем:{" "}
                    <span className="font-semibold">
                      {formatVolumeLiters(item.liters)} л
                    </span>
                  </div>
                  <div className="text-[var(--muted)]">
                    Записей: {formatIntegerRu(item.records_count)}
                  </div>
                </div>
              );
            }}
          />
          <Bar dataKey="liters" fill={barFill} radius={[0, 4, 4, 0]} maxBarSize={22} />
        </BarChart>
      )}
    </MeasureWidth>
  );
}

export type AnalyticsEmployeeBreakdownRow = {
  employee_id: number | null;
  name: string;
  liters: number;
  records_count: number;
};

export function AnalyticsByEmployeeChart(props: {
  rows: AnalyticsEmployeeBreakdownRow[];
}): ReactElement {
  const { rows } = props;

  if (!rows.length) {
    return (
      <div className="mt-3 text-sm text-[var(--muted)]">
        Нет данных по сотрудникам за выбранный период.
      </div>
    );
  }

  const breakdownRows: BreakdownRow[] = rows.map((r) => ({
    key: r.employee_id === null ? "unknown" : String(r.employee_id),
    axisLabel: r.name,
    liters: r.liters,
    records_count: r.records_count,
  }));

  return (
    <HorizontalBreakdownChart rows={breakdownRows} barFill="#6366f1" />
  );
}

export type AnalyticsCarBreakdownRow = {
  car_id: number;
  label: string;
  state_number?: string;
  model?: string;
  liters: number;
  records_count: number;
};

export function AnalyticsByCarChart(props: {
  rows: AnalyticsCarBreakdownRow[];
}): ReactElement {
  const { rows } = props;

  if (!rows.length) {
    return (
      <div className="mt-3 text-sm text-[var(--muted)]">
        Нет данных по автомобилям за выбранный период.
      </div>
    );
  }

  const breakdownRows: BreakdownRow[] = rows.map((r) => ({
    key: String(r.car_id),
    axisLabel: (r.state_number || r.label.split("·")[0] || "").trim(),
    tooltipLabel: r.label,
    liters: r.liters,
    records_count: r.records_count,
  }));

  return <HorizontalBreakdownChart rows={breakdownRows} barFill="#0ea5e9" />;
}
