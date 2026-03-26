import type { CSSProperties } from "react";

export function SkeletonLine({
  height = 14,
  width = "100%",
}: {
  height?: number;
  width?: number | string;
}) {
  const style: CSSProperties =
    typeof width === "number" ? { width, height } : { height, width };

  return <div className="skeleton" style={style} />;
}

