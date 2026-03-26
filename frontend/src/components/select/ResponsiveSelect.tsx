"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";

import { useMediaQueryMinWidth } from "@/hooks/useMediaQueryMinWidth";

export type SelectOption = {
  value: string;
  label: string;
};

export function ResponsiveSelect(props: {
  value: string;
  options: readonly SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  const { value, options, onChange, disabled, ariaLabel } = props;

  const isDesktop = useMediaQueryMinWidth(920);
  const selectedLabel = useMemo(() => {
    return options.find((o) => o.value === value)?.label ?? "—";
  }, [options, value]);

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [popoverTop, setPopoverTop] = useState<number>(0);
  const [popoverLeft, setPopoverLeft] = useState<number>(0);
  const [popoverWidth, setPopoverWidth] = useState<number>(0);
  const [popoverMaxHeight, setPopoverMaxHeight] = useState<number>(320);

  useEffect(() => {
    if (isDesktop) return;
    if (!isOpen) return;

    const updatePosition = () => {
      const el = triggerRef.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      const margin = 8;
      const viewportH = window.innerHeight;
      const viewportW = window.innerWidth;

      const spaceDown = viewportH - rect.bottom - margin;
      const spaceUp = rect.top - margin;

      const shouldOpenDown = spaceDown >= 160 || spaceDown >= spaceUp;
      const maxHeightCandidate = shouldOpenDown ? spaceDown : spaceUp;
      const maxHeight = Math.min(320, Math.max(0, maxHeightCandidate));
      const safeMaxHeight = Math.max(120, maxHeight);

      const maxLeft = Math.max(margin, viewportW - rect.width - margin);
      const clampedLeft = Math.min(Math.max(rect.left, margin), maxLeft);

      setPopoverLeft(clampedLeft);
      setPopoverWidth(rect.width);
      setPopoverMaxHeight(safeMaxHeight);

      const computedTop = shouldOpenDown
        ? rect.bottom + margin
        : Math.max(margin, rect.top - margin - safeMaxHeight);

      const maxTop = Math.max(margin, viewportH - safeMaxHeight - margin);
      const clampedTop = Math.min(Math.max(computedTop, margin), maxTop);

      if (shouldOpenDown) {
        setPopoverTop(clampedTop);
      } else {
        setPopoverTop(clampedTop);
      }
    };

    updatePosition();

    const onScrollOrResize = () => {
      updatePosition();
    };
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);

    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [isOpen, isDesktop]);

  useEffect(() => {
    if (isDesktop) return;
    if (!isOpen) return;

    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (triggerRef.current?.contains(target)) return;
      if (popoverRef.current?.contains(target)) return;
      setIsOpen(false);
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen, isDesktop]);

  if (isDesktop) {
    return (
      <select
        className="input-app"
        value={value}
        aria-label={ariaLabel}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        className="input-app flex items-center justify-between gap-3 disabled:opacity-60"
        style={{ paddingRight: 10 }}
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        onClick={() => {
          if (disabled) return;
          setIsOpen((v) => !v);
        }}
        disabled={disabled}
      >
        <span className="min-w-0 flex-1 truncate text-left">
          {selectedLabel}
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>

      {isOpen ? (
        createPortal(
          <div
            ref={popoverRef}
            role="listbox"
            aria-label={ariaLabel}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] shadow-[var(--shadow-soft)]"
            style={{
              position: "fixed",
              left: popoverLeft,
              top: popoverTop,
              width: popoverWidth,
              maxHeight: popoverMaxHeight,
              overflowY: "auto",
              zIndex: 60,
            }}
          >
            <ul className="m-0 p-1">
              {options.map((opt) => {
                const active = opt.value === value;
                return (
                  <li key={opt.value} className="list-none">
                    <button
                      type="button"
                      role="option"
                      aria-selected={active}
                      className={
                        active
                          ? "w-full rounded-lg bg-[color-mix(in_srgb,var(--primary)_18%,var(--surface-0))] px-2 py-2 text-sm font-semibold"
                          : "w-full rounded-lg px-2 py-2 text-sm font-medium hover:bg-[var(--surface-2)]"
                      }
                      onClick={() => {
                        onChange(opt.value);
                        setIsOpen(false);
                      }}
                    >
                      {opt.label}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>,
          document.body,
        )
      ) : null}
    </div>
  );
}

