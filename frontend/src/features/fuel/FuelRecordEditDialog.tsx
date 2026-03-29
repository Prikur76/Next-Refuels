"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, PencilLine, Save, Trash2, X } from "lucide-react";

import { useMeQuery } from "@/components/auth/useMe";
import { patchFuelRecord, searchCars } from "@/lib/api/endpoints";
import {
  instantIsoToDatetimeLocalInZone,
  normalizeWallDatetimeForApi,
} from "@/lib/datetimeAppTz";
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
  /** Кнопка «на удаление» (заправщик) */
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

  const meQuery = useMeQuery();
  const appTimezone = useMemo(() => {
    return (
      meQuery.data?.app_timezone ||
      process.env.NEXT_PUBLIC_APP_TIME_ZONE ||
      "Europe/Moscow"
    );
  }, [meQuery.data?.app_timezone]);

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
    setFilledLocal(
      instantIsoToDatetimeLocalInZone(initial.filled_at, appTimezone),
    );
    setReportingStatus(initial.reporting_status ?? "ACTIVE");
    setMessage("");
  }, [open, initial, appTimezone]);

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
    const wallAt = normalizeWallDatetimeForApi(filledLocal);
    if (!carId || litersVal === null || !wallAt) {
      setMessage("Заполните авто, литры и дату.");
      return;
    }
    const body: FuelRecordPatchIn = {
      car_id: carId,
      liters: litersVal,
      fuel_type: fuelType,
      source,
      notes,
      filled_at: wallAt,
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
      <div className="flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-t-2xl border border-[var(--border)] bg-[var(--surface-0)] shadow-xl sm:rounded-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--surface-0)] px-4 py-3">
          <h2 id="fuel-edit-title" className="min-w-0 text-sm font-semibold">
            <span className="inline-flex items-center gap-2">
              <PencilLine size={18} aria-hidden className="shrink-0" />
              <span className="break-words">
                Редактирование заправки #{initial.id}
              </span>
            </span>
          </h2>
          <button
            type="button"
            className="shrink-0 rounded-lg p-2 text-[var(--muted)] hover:bg-[var(--surface-1)]"
            aria-label="Закрыть"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain p-4">
          <div className="space-y-3">
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

          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="label-app min-w-0">
              Литры
              <input
                className="input-app min-w-0 max-w-full"
                value={liters}
                onChange={(e) => setLiters(e.target.value)}
                inputMode="decimal"
              />
            </label>
            <label className="label-app min-w-0">
              Дата и время заправки
              <input
                type="datetime-local"
                className="input-app min-w-0 max-w-full"
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

          {/* Мобильная версия: только иконки */}
          <div
            className={`grid gap-2 pt-2 sm:hidden ${
              showExclusionActions ? "grid-cols-2" : "grid-cols-1"
            }`}
          >
            <button
              type="button"
              className="btn-app btn-primary inline-flex min-h-12 items-center justify-center px-3 py-3"
              disabled={saveMutation.isPending}
              aria-label="Сохранить"
              title="Сохранить"
              onClick={handleSave}
            >
              {saveMutation.isPending ? (
                <Loader2 className="animate-spin" size={22} aria-hidden />
              ) : (
                <Save size={22} strokeWidth={2} aria-hidden />
              )}
            </button>
            {showExclusionActions ? (
              <button
                type="button"
                className="btn-app inline-flex min-h-12 items-center justify-center border border-red-300 bg-red-50 px-3 py-3 text-red-600 dark:border-red-800 dark:bg-red-950/40 dark:text-red-400"
                disabled={saveMutation.isPending}
                aria-label="На удаление"
                title="На удаление"
                onClick={() => markStatus("EXCLUDED_DELETION")}
              >
                <Trash2 size={22} strokeWidth={2} aria-hidden />
              </button>
            ) : null}
          </div>

          {/* Планшет и десктоп: подписи на кнопках */}
          <div className="hidden flex-col gap-2 pt-2 sm:flex sm:flex-row sm:flex-wrap">
            <button
              type="button"
              className="btn-app btn-primary inline-flex flex-1 items-center justify-center gap-2"
              disabled={saveMutation.isPending}
              onClick={handleSave}
            >
              {saveMutation.isPending ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <Save size={18} aria-hidden />
              )}
              Сохранить
            </button>
            {showExclusionActions ? (
              <button
                type="button"
                className="btn-app inline-flex flex-1 items-center justify-center gap-2 border border-red-300 bg-red-50 text-red-600 dark:border-red-800 dark:bg-red-950/40 dark:text-red-400 sm:flex-initial"
                disabled={saveMutation.isPending}
                onClick={() => markStatus("EXCLUDED_DELETION")}
              >
                <Trash2 size={18} aria-hidden />
                На удаление
              </button>
            ) : null}
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
