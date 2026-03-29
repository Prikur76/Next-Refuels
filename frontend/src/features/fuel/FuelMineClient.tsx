"use client";

import { useState } from "react";
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
        <div className="muted-box mt-3 text-sm text-[var(--muted)]">
          <p>
            Вы можете изменить записи о своих заправках в течение{" "}
            <strong>24 часов</strong> с момента указанного времени заправки — в
            часовом поясе вашего браузера. По истечении этого срока правки
            доступны только <strong>менеджеру вашего региона</strong>.
          </p>
          <p className="mt-2">
            Записи, помеченные как дубликат или на удаление, не показываются в
            отчётах и не участвуют в итогах.
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
            <div className="overflow-x-auto">
              <table className="table-app">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Авто</th>
                    <th>Л</th>
                    <th>Топливо</th>
                    <th>Источник</th>
                    <th>Комментарий</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {listQuery.data.map((row) => (
                    <tr key={row.id}>
                      <td className="mono text-sm">
                        {formatLocalDateTime(row.filled_at)}
                      </td>
                      <td>{row.car_state_number}</td>
                      <td>{formatDecimalRu(row.liters)}</td>
                      <td>{row.fuel_type === "DIESEL" ? "Дизель" : "Бензин"}</td>
                      <td>{sourceLabel(row.source)}</td>
                      <td className="max-w-[180px] truncate text-sm">
                        {row.notes || "—"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-app inline-flex items-center gap-1 border border-[var(--border)] text-xs"
                          onClick={() => setEditing(recordToInitial(row))}
                        >
                          <PencilLine size={14} />
                          Изменить
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
