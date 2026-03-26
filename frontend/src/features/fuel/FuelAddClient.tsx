"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  Info,
  Loader2,
  Save,
  Search,
  Trash2,
} from "lucide-react";

import { createFuelRecord, searchCars } from "@/lib/api/endpoints";
import type { FuelRecordIn, FuelSource, FuelType } from "@/lib/api/types";
import { SkeletonLine } from "@/components/skeleton/Skeleton";
import { ResponsiveSelect } from "@/components/select/ResponsiveSelect";

const INITIAL_SOURCE: FuelSource = "TGBOT";
const INITIAL_FUEL_TYPE: FuelType = "GASOLINE";

type FuelFormState = {
  car_id: number | null;
  liters: string;
  fuel_type: FuelType;
  source: FuelSource;
  notes: string;
};

type FuelEntryStep = "car" | "details";

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

const fadeSlide = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.2, ease: "easeOut" as const },
};

function normalizeStateNumberInput(raw: string): string {
  const upper = raw.toUpperCase();
  const converted = Array.from(upper, (char) => {
    return LATIN_TO_CYRILLIC_MAP[char] ?? char;
  }).join("");
  return converted.replace(/\s+/g, "");
}

function formatLiters(raw: string): number | null {
  const normalized = raw.replace(",", ".").trim();
  if (!normalized) return null;
  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

export function FuelAddClient() {
  const [carQuery, setCarQuery] = useState("");
  const [step, setStep] = useState<FuelEntryStep>("car");
  const [form, setForm] = useState<FuelFormState>({
    car_id: null,
    liters: "",
    fuel_type: INITIAL_FUEL_TYPE,
    source: INITIAL_SOURCE,
    notes: "",
  });
  const [statusMsg, setStatusMsg] = useState<string>("");
  const normalizedCarQuery = useMemo(
    () => normalizeStateNumberInput(carQuery),
    [carQuery]
  );

  const carsQuery = useQuery({
    queryKey: ["cars", normalizedCarQuery],
    queryFn: () => searchCars(normalizedCarQuery, 20),
    enabled: normalizedCarQuery.length > 0,
  });

  const foundCar = useMemo(() => {
    const cars = carsQuery.data ?? [];
    if (!cars.length) return null;
    const exactMatch = cars.find(
      (car) => normalizeStateNumberInput(car.state_number) === normalizedCarQuery
    );
    const candidate = exactMatch ?? cars[0];
    return {
      id: candidate.id,
      state_number: candidate.state_number,
      model: candidate.model,
      region_name: candidate.region_name ?? null,
    };
  }, [carsQuery.data, normalizedCarQuery]);

  const carsCount = carsQuery.data?.length ?? 0;
  const canConfirmFoundCar =
    normalizedCarQuery.length > 0 &&
    !carsQuery.isPending &&
    Boolean(foundCar) &&
    carsCount === 1;

  const mutation = useMutation({
    mutationFn: (payload: FuelRecordIn) => createFuelRecord(payload),
    onSuccess: () => {
      setStatusMsg("Запись успешно сохранена.");
      setForm({
        car_id: null,
        liters: "",
        fuel_type: INITIAL_FUEL_TYPE,
        source: INITIAL_SOURCE,
        notes: "",
      });
      setCarQuery("");
      setStep("car");
    },
    onError: (err) => {
      setStatusMsg((err as Error).message || "Ошибка отправки.");
    },
  });

  const isSubmitDisabled = useMemo(() => {
    if (!form.car_id) return true;
    if (!formatLiters(form.liters)) return true;
    return mutation.isPending;
  }, [form.car_id, form.liters, mutation.isPending]);

  return (
    <div className="page-wrap">
      <section className="card p-4">
        <h1 className="section-title">Новая заправка</h1>
        <p className="section-subtitle mt-1">
          Пошаговый ввод: сначала проверка авто, затем параметры заправки.
        </p>

        <div className="mt-4 stack">
          <div className="muted-box text-sm">
            <span className="font-semibold">Шаг 1.</span> Проверка автомобиля
          </div>

          <label className="label-app">
            Госномер машины
            <input
              className="input-app"
              value={carQuery}
              onChange={(e) => {
                const nextValue = normalizeStateNumberInput(e.target.value);
                setCarQuery(nextValue);
                setStep("car");
                setForm((prev) => ({ ...prev, car_id: null }));
              }}
              placeholder="Например, А123ВС77"
              autoComplete="off"
              inputMode="text"
            />
          </label>
          <div className="text-xs text-[var(--muted)]">
            Можно вводить латиницей и в любом регистре, номер нормализуется
            автоматически.
          </div>

          <AnimatePresence mode="popLayout">
            {normalizedCarQuery.length > 0 && carsQuery.isFetching ? (
              <motion.div key="cars-loading" {...fadeSlide} className="space-y-2">
                <SkeletonLine height={16} width={220} />
                <SkeletonLine height={16} width={200} />
                <SkeletonLine height={16} width={190} />
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {normalizedCarQuery.length > 0 &&
            !carsQuery.isPending &&
            carsCount === 0 ? (
              <motion.div key="no-results" {...fadeSlide} className="muted-box text-sm">
                <span className="inline-flex items-center gap-2 text-[var(--muted)]">
                  <Search size={15} aria-hidden="true" />
                  <span>Ничего не найдено. Уточните номер авто.</span>
                </span>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {carsCount > 1 ? (
              <motion.div key="many-results" {...fadeSlide} className="stack">
                <div className="text-sm font-semibold">Найдено: {carsCount}</div>
                <div className="space-y-2">
                  {(carsQuery.data ?? []).map((car) => {
                    return (
                      <div key={car.id} className="muted-box">
                        <div className="font-semibold">
                          {car.state_number} · {car.model}
                        </div>
                        <div className="text-xs text-[var(--muted)]">
                          Регион: {car.region_name || "не указан"}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="text-xs text-[var(--muted)] inline-flex items-center gap-1">
                  <Info size={14} aria-hidden="true" />
                  Уточните номер, чтобы остался один вариант.
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {foundCar && carsCount === 1 ? (
              <motion.div
                key="single-result"
                {...fadeSlide}
                className="muted-box text-sm text-[var(--muted)]"
              >
                Найден автомобиль:{" "}
                <span className="font-semibold">
                  {`${foundCar.state_number} · ${foundCar.model} · ${
                    foundCar.region_name || "регион не указан"
                  }`}
                </span>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {canConfirmFoundCar ? (
              <motion.div key="confirm-btn" {...fadeSlide} className="toolbar">
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  className="btn-app btn-primary"
                  aria-disabled={mutation.isPending}
                  onClick={() => {
                    if (!foundCar) return;
                    setForm((prev) => ({
                      ...prev,
                      car_id: foundCar.id,
                    }));
                    setStep("details");
                  }}
                >
                  <span className="inline-flex items-center gap-2">
                    <CheckCircle2 size={16} aria-hidden="true" />
                    <span>Подтвердить авто</span>
                  </span>
                </motion.button>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {step === "details" ? (
              <motion.div key="step-details" {...fadeSlide} className="stack">
                <div className="muted-box text-sm">
                <span className="font-semibold">Шаг 2.</span> Введите параметры
                заправки
                </div>

              <div
                className="grid gap-3"
                style={{
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                }}
              >
                <label className="label-app">
                  Количество топлива (литры)
                  <input
                    className="input-app"
                    value={form.liters}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, liters: e.target.value }))
                    }
                    placeholder="45.5"
                    inputMode="decimal"
                  />
                </label>

                <label className="label-app">
                  Источник
                  <ResponsiveSelect
                    ariaLabel="Источник"
                    value={form.source}
                    onChange={(v) =>
                      setForm((prev) => ({
                        ...prev,
                        source: v as FuelSource,
                      }))
                    }
                    options={[
                      { value: "TGBOT", label: "Телеграм-бот" },
                      { value: "CARD", label: "Топливная карта" },
                      {
                        value: "TRUCK",
                        label: "Топливозаправщик",
                      },
                    ]}
                  />
                </label>

                <label className="label-app">
                  Тип топлива
                  <ResponsiveSelect
                    ariaLabel="Тип топлива"
                    value={form.fuel_type}
                    onChange={(v) =>
                      setForm((prev) => ({
                        ...prev,
                        fuel_type: v as FuelType,
                      }))
                    }
                    options={[
                      { value: "GASOLINE", label: "Бензин" },
                      { value: "DIESEL", label: "Дизель" },
                    ]}
                  />
                </label>

                <label className="label-app" style={{ gridColumn: "1 / -1" }}>
                  Комментарий (опционально)
                  <textarea
                    className="input-app"
                    value={form.notes}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, notes: e.target.value }))
                    }
                    placeholder="Необязательно"
                  />
                </label>
              </div>

              <div className="mt-2 toolbar fuel-actions-toolbar">
                <button
                  type="button"
                  className="btn-app fuel-action-btn"
                  onClick={() => setStep("car")}
                  title="К поиску"
                  aria-label="К поиску"
                >
                  <span className="inline-flex items-center gap-2">
                    <ArrowLeft size={16} aria-hidden="true" />
                    <span className="hidden sm:inline">К поиску</span>
                  </span>
                </button>
                <button
                  type="button"
                  className="btn-app btn-primary fuel-action-btn fuel-action-btn-save"
                  aria-disabled={isSubmitDisabled}
                  title={mutation.isPending ? "Сохраняем..." : "Сохранить"}
                  aria-label={mutation.isPending ? "Сохраняем..." : "Сохранить"}
                  onClick={() => {
                    if (!form.car_id) return;
                    const litersValue = formatLiters(form.liters);
                    if (!litersValue) return;
                    const payload: FuelRecordIn = {
                      car_id: form.car_id,
                      liters: litersValue,
                      fuel_type: form.fuel_type,
                      source: form.source,
                      notes: form.notes,
                    };
                    setStatusMsg("");
                    mutation.mutate(payload);
                  }}
                >
                  <span className="inline-flex items-center gap-2">
                    {mutation.isPending ? (
                      <Loader2
                        size={16}
                        className="animate-spin"
                        aria-hidden="true"
                      />
                    ) : (
                      <Save size={16} aria-hidden="true" />
                    )}
                    <span className="hidden sm:inline">
                      {mutation.isPending ? "Сохраняем..." : "Сохранить"}
                    </span>
                    <span className="visually-hidden">
                      {mutation.isPending ? "Сохраняем..." : "Сохранить"}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="btn-app fuel-action-btn"
                  title="Сброс"
                  aria-label="Сброс"
                  onClick={() => {
                    setCarQuery("");
                    setForm({
                      car_id: null,
                      liters: "",
                      fuel_type: INITIAL_FUEL_TYPE,
                      source: INITIAL_SOURCE,
                      notes: "",
                    });
                    setStep("car");
                    setStatusMsg("");
                  }}
                >
                  <span className="inline-flex items-center gap-2">
                    <Trash2 size={16} aria-hidden="true" />
                    <span className="hidden sm:inline">Сброс</span>
                  </span>
                </button>
              </div>
              </motion.div>
          ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {mutation.isPending ? (
              <motion.div
                key="saving-progress"
                {...fadeSlide}
                className="muted-box text-sm text-[var(--muted)]"
              >
                <span className="inline-flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  <span>Сохраняем данные, подождите...</span>
                </span>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            {statusMsg ? (
              <motion.div
                key="status-msg"
                {...fadeSlide}
                className="muted-box text-sm text-[var(--muted)]"
              >
                {statusMsg}
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </section>
    </div>
  );
}

