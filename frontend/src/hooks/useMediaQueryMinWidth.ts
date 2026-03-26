"use client";

import { useSyncExternalStore } from "react";

function subscribeMinWidth(px: number, onChange: () => void): () => void {
  const mq = window.matchMedia(`(min-width: ${px}px)`);
  mq.addEventListener("change", onChange);
  return () => {
    mq.removeEventListener("change", onChange);
  };
}

function getMinWidthSnapshot(px: number): boolean {
  return window.matchMedia(`(min-width: ${px}px)`).matches;
}

/**
 * SSR / первый рендер: false (mobile-first), затем фактическое значение.
 */
export function useMediaQueryMinWidth(minWidthPx: number): boolean {
  return useSyncExternalStore(
    (onStoreChange) => subscribeMinWidth(minWidthPx, onStoreChange),
    () => getMinWidthSnapshot(minWidthPx),
    () => false,
  );
}
