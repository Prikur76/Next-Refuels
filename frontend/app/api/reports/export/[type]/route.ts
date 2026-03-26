import { NextRequest, NextResponse } from "next/server";

type ExportType = "csv" | "xlsx";

function isExportType(value: string): value is ExportType {
  return value === "csv" || value === "xlsx";
}

function getBackendBaseUrl(): string {
  const raw =
    process.env.NEXT_INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ type: string }> }
) {
  const { type } = await context.params;
  if (!isExportType(type)) {
    return NextResponse.json({ detail: "Unsupported export type" }, { status: 400 });
  }

  const backendBaseUrl = getBackendBaseUrl();
  const upstreamUrl = new URL(
    `${backendBaseUrl}/api/v1/reports/export/${type}/`
  );
  upstreamUrl.search = request.nextUrl.search;

  const upstream = await fetch(upstreamUrl.toString(), {
    method: "GET",
    headers: {
      cookie: request.headers.get("cookie") ?? "",
    },
    redirect: "follow",
    cache: "no-store",
  });

  if (!upstream.ok) {
    const detail = await upstream.text();
    return NextResponse.json(
      { detail: detail || `Export failed with status ${upstream.status}` },
      { status: upstream.status }
    );
  }

  const body = await upstream.arrayBuffer();
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  const contentDisposition = upstream.headers.get("content-disposition");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (contentDisposition) {
    headers.set("content-disposition", contentDisposition);
  }

  return new NextResponse(body, {
    status: 200,
    headers,
  });
}
