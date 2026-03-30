"use client";

import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PencilLine } from "lucide-react";

import { getMyFuelRecords } from "@/lib/api/endpoints";
import type { FuelRecordOut, FuelSource, FuelType } from "@/lib/api/types";
import { SkeletonLine } from "@/components/skeleton/Skeleton";
import {
  FuelRecordEditDialog,
  type FuelRecordEditInitial,
} from "@/features/fuel/FuelRecordEditDialog";
import { formatDecimalRu } from "@/lib/format-number-ru";
import {
  isSuspiciousNonTankerRefuel,
  SUSPICIOUS_REFUEL_ROW_TITLE,
  suspiciousRefuelCardClass,
  suspiciousRefuelTableRowClass,
} from "@/lib/fuelSuspiciousLiters";

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

function sourceLabel(code: string): string {
  const m: Record<string, string> = {
    TGBOT: "ТГ-бот",
    CARD: "Карта",
    TRUCK: "ТЗ",
  };
  return m[code] ?? code;
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

function recordToInitial(row: FuelRecordOut): FuelRecordEditInitial {
  return {
    id: row.id,
    car_id: row.car_id,
    car_state_number: row.car_state_number,
    liters: row.liters,
    fuel_type: row.fuel_type as FuelType,
    source: row.source as FuelSource,
    notes: row.notes ?? "",
    filled_at: row.filled_at,
    reporting_status: row.reporting_status,
  };
}

function reportingStatusLabel(status: string | undefined): string {
  if (status === "EXCLUDED_DELETION") {
    return "На удаление";
  }
  return "Учитывается";
}

function reportingStatusBadgeClass(status: string | undefined): string {
  if (status === "EXCLUDED_DELETION") {
    return "inline-flex items-center rounded-md border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300";
  }
  return "inline-flex items-center rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300";
}

export function FuelMineClient() {
  const [editing, setEditing] = useState<FuelRecordEditInitial | null>(null);
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ["fuel-records", "mine"],
    queryFn: getMyFuelRecords,
  });

  return (
    <div className="page-wrap">
      <section className="card p-4">
        <h1 className="section-title">Мои заправки</h1>
        <div className="fuel-mine-hint mt-3">
          <p>
            Правки доступны в течение 24 часов с момента заправки (ваш локальный
            часовой пояс). Позже уточнения - через регионального менеджера.
          </p>
        </div>

        <div className="mt-4">
          {listQuery.isPending ? (
            <div className="space-y-2">
              <SkeletonLine height={16} width="100%" />
              <SkeletonLine height={16} width="90%" />
            </div>
          ) : listQuery.isError ? (
            <div className="text-sm text-red-600 dark:text-red-400">
              {(listQuery.error as Error).message ||
                "Не удалось загрузить список."}
            </div>
          ) : !listQuery.data?.length ? (
            <div className="text-sm text-[var(--muted)]">
              Нет доступных для правки записей за последние 24 часа.
            </div>
          ) : (
            <>
              <div className="hidden lg:block overflow-x-auto">
                <table className="table-app table-app--fuel-gap">
                  <thead>
                    <tr>
                      <th>Дата</th>
                      <th>Авто</th>
                      <th>Л</th>
                      <th>Топливо</th>
                      <th>Источник</th>
                      <th>Статус</th>
                      <th>Комментарий</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {listQuery.data.map((row) => {
                      const suspicious = isSuspiciousNonTankerRefuel(
                        row.car_is_fuel_tanker,
                        row.liters,
                      );
                      return (
                      <tr
                        key={row.id}
                        className={suspiciousRefuelTableRowClass(suspicious)}
                        title={suspicious ? SUSPICIOUS_REFUEL_ROW_TITLE : undefined}
                      >
                        <td className="mono text-sm">
                          {formatLocalDateTime(row.filled_at)}
                        </td>
                        <td
                          className={fuelTankerPlateClass(
                            row.car_is_fuel_tanker,
                          )}
                        >
                          {renderCarPlateWithBadge(
                            row.car_state_number,
                            row.car_is_fuel_tanker,
                          )}
                        </td>
                        <td>{formatDecimalRu(row.liters)}</td>
                        <td>
                          {row.fuel_type === "DIESEL" ? "Дизель" : "Бензин"}
                        </td>
                        <td>{sourceLabel(row.source)}</td>
                        <td>
                          <span
                            className={reportingStatusBadgeClass(
                              row.reporting_status,
                            )}
                            title={row.reporting_status ?? "ACTIVE"}
                          >
                            {reportingStatusLabel(row.reporting_status)}
                          </span>
                        </td>
                        <td className="max-w-[180px] truncate text-sm">
                          {row.notes || "—"}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-app inline-flex items-center justify-center !p-2 border border-[var(--border)]"
                            aria-label="Изменить"
                            title="Изменить"
                            onClick={() => setEditing(recordToInitial(row))}
                          >
                            <PencilLine size={14} aria-hidden />
                          </button>
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="space-y-3 lg:hidden">
                {listQuery.data.map((row) => {
                  const suspicious = isSuspiciousNonTankerRefuel(
                    row.car_is_fuel_tanker,
                    row.liters,
                  );
                  return (
                  <article
                    key={row.id}
                    className={
                      "rounded-xl p-3 sm:p-4 " +
                      (suspicious
                        ? suspiciousRefuelCardClass(true)
                        : "border border-[var(--border)] bg-[var(--surface-0)]")
                    }
                    title={suspicious ? SUSPICIOUS_REFUEL_ROW_TITLE : undefined}
                  >
                    <div className="mono text-xs text-[var(--muted)]">
                      {formatLocalDateTime(row.filled_at)}
                    </div>
                    <div className="mt-3 space-y-2 text-sm">
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Авто
                        </span>
                        <span
                          className={`min-w-0 break-words text-right ${fuelTankerPlateClass(
                            row.car_is_fuel_tanker,
                          )}`}
                        >
                          {renderCarPlateWithBadge(
                            row.car_state_number,
                            row.car_is_fuel_tanker,
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Объем
                        </span>
                        <span className="font-semibold tabular-nums">
                          {formatDecimalRu(row.liters)} л
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Топливо
                        </span>
                        <span className="min-w-0 break-words text-right">
                          {row.fuel_type === "DIESEL" ? "Дизель" : "Бензин"}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Источник
                        </span>
                        <span className="min-w-0 break-words text-right">
                          {sourceLabel(row.source)}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Комментарий
                        </span>
                        <span className="min-w-0 break-words text-right">
                          {row.notes?.trim() ? row.notes : "—"}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="shrink-0 text-[var(--muted)]">
                          Статус
                        </span>
                        <span className="min-w-0 break-words text-right">
                          <span
                            className={reportingStatusBadgeClass(
                              row.reporting_status,
                            )}
                          >
                            {reportingStatusLabel(row.reporting_status)}
                          </span>
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-app mt-3 w-full inline-flex items-center justify-center gap-2 border border-[var(--border)] text-sm"
                      onClick={() => setEditing(recordToInitial(row))}
                    >
                      <PencilLine size={16} aria-hidden />
                      Изменить
                    </button>
                  </article>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </section>

      <FuelRecordEditDialog
        open={editing !== null}
        initial={editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          void listQuery.refetch();
          void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
        }}
        showExclusionActions
      />
    </div>
  );
}
