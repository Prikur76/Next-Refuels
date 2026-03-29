"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, PencilLine, X } from "lucide-react";

import { patchFuelRecord, searchCars } from "@/lib/api/endpoints";
import type {
  FuelRecordPatchIn,
  FuelReportingStatus,
  FuelSource,
  FuelType,
} from "@/lib/api/types";
import { ResponsiveSelect } from "@/components/select/ResponsiveSelect";
import { SkeletonLine } from "@/components/skeleton/Skeleton";

const LATIN_TO_CYRILLIC_MAP: Record<string, string> = {
  A: "А",
  B: "В",
  C: "С",
  E: "Е",
  H: "Н",
  K: "К",
  M: "М",
  O: "О",
  P: "Р",
  T: "Т",
  X: "Х",
  Y: "У",
};

function normalizeStateNumberInput(raw: string): string {
  const upper = raw.toUpperCase();
  const converted = Array.from(upper, (char) => {
    return LATIN_TO_CYRILLIC_MAP[char] ?? char;
  }).join("");
  return converted.replace(/\s+/g, "");
}

function parseLitersInput(raw: string): number | null {
  const normalized = raw.replace(",", ".").trim();
  if (!normalized) return null;
  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

function isoToDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

function datetimeLocalToIso(local: string): string {
  const d = new Date(local);
  return d.toISOString();
}

export type FuelRecordEditInitial = {
  id: number;
  car_id: number;
  car_state_number: string;
  liters: number | string;
  fuel_type: FuelType;
  source: FuelSource;
  notes: string;
  filled_at: string;
  reporting_status?: FuelReportingStatus;
};

type FuelRecordEditDialogProps = {
  open: boolean;
  initial: FuelRecordEditInitial | null;
  onClose: () => void;
  onSaved: () => void;
  /** Кнопки «дубликат» / «на удаление» (заправщик) */
  showExclusionActions?: boolean;
  /** Поле статуса учёта (менеджер / админ) */
  showReportingField?: boolean;
};

export function FuelRecordEditDialog(props: FuelRecordEditDialogProps) {
  const {
    open,
    initial,
    onClose,
    onSaved,
    showExclusionActions = false,
    showReportingField = false,
  } = props;

  const [carQuery, setCarQuery] = useState("");
  const [carId, setCarId] = useState<number | null>(null);
  const [liters, setLiters] = useState("");
  const [fuelType, setFuelType] = useState<FuelType>("GASOLINE");
  const [source, setSource] = useState<FuelSource>("TGBOT");
  const [notes, setNotes] = useState("");
  const [filledLocal, setFilledLocal] = useState("");
  const [reportingStatus, setReportingStatus] =
    useState<FuelReportingStatus>("ACTIVE");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!open || !initial) return;
    setCarQuery(normalizeStateNumberInput(initial.car_state_number));
    setCarId(initial.car_id);
    setLiters(String(initial.liters));
    setFuelType(initial.fuel_type);
    setSource(initial.source);
    setNotes(initial.notes ?? "");
    setFilledLocal(isoToDatetimeLocalValue(initial.filled_at));
    setReportingStatus(initial.reporting_status ?? "ACTIVE");
    setMessage("");
  }, [open, initial]);

  const normalizedCarQuery = useMemo(
    () => normalizeStateNumberInput(carQuery),
    [carQuery],
  );

  const carsQuery = useQuery({
    queryKey: ["cars", "edit", normalizedCarQuery],
    queryFn: () => searchCars(normalizedCarQuery, 20),
    enabled: open && normalizedCarQuery.length > 0,
  });

  const foundCar = useMemo(() => {
    const cars = carsQuery.data ?? [];
    if (!cars.length) return null;
    const exactMatch = cars.find(
      (c) => normalizeStateNumberInput(c.state_number) === normalizedCarQuery,
    );
    const candidate = exactMatch ?? cars[0];
    return candidate;
  }, [carsQuery.data, normalizedCarQuery]);

  const carsCount = carsQuery.data?.length ?? 0;

  const saveMutation = useMutation({
    mutationFn: (body: FuelRecordPatchIn) =>
      initial ? patchFuelRecord(initial.id, body) : Promise.reject(),
    onSuccess: () => {
      setMessage("Сохранено.");
      onSaved();
      onClose();
    },
    onError: (err: Error) => {
      setMessage(err.message || "Ошибка сохранения.");
    },
  });

  if (!open || !initial) {
    return null;
  }

  function handleSave(): void {
    const litersVal = parseLitersInput(liters);
    if (!carId || litersVal === null || !filledLocal) {
      setMessage("Заполните авто, литры и дату.");
      return;
    }
    const body: FuelRecordPatchIn = {
      car_id: carId,
      liters: litersVal,
      fuel_type: fuelType,
      source,
      notes,
      filled_at: datetimeLocalToIso(filledLocal),
    };
    if (showReportingField) {
      body.reporting_status = reportingStatus;
    }
    saveMutation.mutate(body);
  }

  function markStatus(st: FuelReportingStatus): void {
    saveMutation.mutate({ reporting_status: st });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="fuel-edit-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-2xl border border-[var(--border)] bg-[var(--surface-0)] shadow-xl sm:rounded-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface-0)] px-4 py-3">
          <h2 id="fuel-edit-title" className="text-sm font-semibold">
            <span className="inline-flex items-center gap-2">
              <PencilLine size={18} aria-hidden />
              Редактирование заправки #{initial.id}
            </span>
          </h2>
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--muted)] hover:bg-[var(--surface-1)]"
            aria-label="Закрыть"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3 p-4">
          <label className="label-app">
            Госномер
            <input
              className="input-app"
              value={carQuery}
              onChange={(e) => {
                const v = normalizeStateNumberInput(e.target.value);
                setCarQuery(v);
                setCarId(null);
              }}
              autoComplete="off"
            />
          </label>
          {normalizedCarQuery.length > 0 && carsQuery.isFetching ? (
            <div className="space-y-2">
              <SkeletonLine height={14} width="100%" />
            </div>
          ) : null}
          {normalizedCarQuery.length > 0 &&
          !carsQuery.isFetching &&
          carsCount === 1 &&
          foundCar ? (
            <div className="muted-box text-xs">
              Найдено: {foundCar.state_number} · {foundCar.model}
              <button
                type="button"
                className="btn-app btn-primary mt-2 w-full text-xs"
                onClick={() => setCarId(foundCar.id)}
              >
                Привязать это авто
              </button>
            </div>
          ) : null}
          {carsCount > 1 ? (
            <div className="text-xs text-[var(--muted)]">
              Уточните номер — найдено несколько вариантов.
            </div>
          ) : null}

          {carId === null ? (
            <div className="text-xs text-amber-700 dark:text-amber-300">
              Укажите номер и привяжите автомобиль.
            </div>
          ) : null}

          <div
            className="grid gap-3"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            }}
          >
            <label className="label-app">
              Литры
              <input
                className="input-app"
                value={liters}
                onChange={(e) => setLiters(e.target.value)}
                inputMode="decimal"
              />
            </label>
            <label className="label-app">
              Дата и время заправки
              <input
                type="datetime-local"
                className="input-app"
                value={filledLocal}
                onChange={(e) => setFilledLocal(e.target.value)}
              />
            </label>
          </div>

          <label className="label-app">
            Тип топлива
            <ResponsiveSelect
              ariaLabel="Тип топлива"
              value={fuelType}
              onChange={(v) => setFuelType(v as FuelType)}
              options={[
                { value: "GASOLINE", label: "Бензин" },
                { value: "DIESEL", label: "Дизель" },
              ]}
            />
          </label>

          <label className="label-app">
            Способ заправки
            <ResponsiveSelect
              ariaLabel="Способ заправки"
              value={source}
              onChange={(v) => setSource(v as FuelSource)}
              options={[
                { value: "CARD", label: "Карта" },
                { value: "TGBOT", label: "Telegram-бот" },
                { value: "TRUCK", label: "Топливозаправщик" },
              ]}
            />
          </label>

          <label className="label-app">
            Комментарий
            <textarea
              className="input-app min-h-[72px]"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>

          {showReportingField ? (
            <label className="label-app">
              Статус в отчётах
              <ResponsiveSelect
                ariaLabel="Статус в отчётах"
                value={reportingStatus}
                onChange={(v) =>
                  setReportingStatus(v as FuelReportingStatus)
                }
                options={[
                  { value: "ACTIVE", label: "Учитывается" },
                  {
                    value: "EXCLUDED_DUPLICATE",
                    label: "Исключить (дубликат)",
                  },
                  {
                    value: "EXCLUDED_DELETION",
                    label: "На удаление (не учитывать)",
                  },
                ]}
              />
            </label>
          ) : null}

          {message ? (
            <div className="text-sm text-[var(--muted)]">{message}</div>
          ) : null}

          <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:flex-wrap">
            <button
              type="button"
              className="btn-app btn-primary inline-flex flex-1 items-center justify-center gap-2"
              disabled={saveMutation.isPending}
              onClick={handleSave}
            >
              {saveMutation.isPending ? (
                <Loader2 className="animate-spin" size={18} />
              ) : null}
              Сохранить
            </button>
            {showExclusionActions ? (
              <>
                <button
                  type="button"
                  className="btn-app border border-[var(--border)]"
                  disabled={saveMutation.isPending}
                  onClick={() => markStatus("EXCLUDED_DUPLICATE")}
                >
                  Дубликат
                </button>
                <button
                  type="button"
                  className="btn-app border border-[var(--border)]"
                  disabled={saveMutation.isPending}
                  onClick={() => markStatus("EXCLUDED_DELETION")}
                >
                  На удаление
                </button>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
