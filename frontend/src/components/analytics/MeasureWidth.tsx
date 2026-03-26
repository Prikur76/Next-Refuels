"use client";

import {
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactElement,
  type ReactNode,
} from "react";

export function MeasureWidth(props: {
  className?: string;
  style?: CSSProperties;
  children: (widthPx: number) => ReactNode;
  fallback?: ReactNode;
}): ReactElement {
  const { className, style, children, fallback = null } = props;
  const ref = useRef<HTMLDivElement | null>(null);
  const [widthPx, setWidthPx] = useState(0);

  useLayoutEffect(() => {
    const node = ref.current;
    if (node === null) {
      return;
    }

    function readWidth(): void {
      const el = ref.current;
      if (el === null) {
        return;
      }

      const next = Math.floor(el.getBoundingClientRect().width);
      setWidthPx((prev) => (prev === next ? prev : next));
    }

    readWidth();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => {
      readWidth();
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <div ref={ref} className={className} style={style}>
      {widthPx > 0 ? children(widthPx) : fallback}
    </div>
  );
}
