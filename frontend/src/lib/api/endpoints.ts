"use client";

import { apiFetchJson } from "./client";
import type {
  AccessLogOut,
  AccessPasswordOut,
  AccessPasswordPatchIn,
  AccessUserProfilePatchIn,
  AccessRole,
  AccessRolePatchIn,
  AccessStatusPatchIn,
  AccessUserCreateIn,
  AccessUserCreateOut,
  AccessUserOut,
  CarOut,
  FuelRecordIn,
  FuelRecordOut,
  FuelRecordPatchIn,
  RegionOut,
  ReportsFiltersOut,
  RecordsPageOut,
  SummaryOut,
  TelegramLinkCodeOut,
  PasswordSetupIn,
  PasswordSetupOut,
  UserMeOut,
} from "./types";

export async function getMe(): Promise<UserMeOut> {
  const params = new URLSearchParams();
  if (typeof window !== "undefined") {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) {
        params.set("client_tz", tz);
      }
    } catch {
      // ignore
    }
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiFetchJson<UserMeOut>(`/api/v1/auth/me${suffix}`);
}

export async function createTelegramLinkCode(): Promise<TelegramLinkCodeOut> {
  return apiFetchJson<TelegramLinkCodeOut>("/api/v1/auth/telegram/link-code", {
    method: "POST",
  });
}

export async function searchCars(
  query: string,
  limit = 20
): Promise<CarOut[]> {
  const params = new URLSearchParams({
    query,
    limit: String(limit),
  });
  return apiFetchJson<CarOut[]>(`/api/v1/cars?${params.toString()}`);
}

export async function createFuelRecord(
  payload: FuelRecordIn
): Promise<FuelRecordOut> {
  return apiFetchJson<FuelRecordOut>("/api/v1/fuel-records", {
    method: "POST",
    body: payload,
  });
}

export async function getMyFuelRecords(): Promise<FuelRecordOut[]> {
  return apiFetchJson<FuelRecordOut[]>("/api/v1/fuel-records/mine", {
    clientTimezone: true,
  });
}

export async function patchFuelRecord(
  recordId: number,
  payload: FuelRecordPatchIn
): Promise<FuelRecordOut> {
  return apiFetchJson<FuelRecordOut>(
    `/api/v1/fuel-records/${recordId}`,
    {
      method: "PATCH",
      body: payload,
      clientTimezone: true,
    }
  );
}

export async function getSummary(filters: {
  from_date?: string;
  to_date?: string;
  region_id?: number;
  region?: string;
  employee?: string;
  car_id?: number;
  car_state_number?: string;
  source?: string;
  include_excluded?: boolean;
}): Promise<SummaryOut> {
  const params = new URLSearchParams();
  if (filters.from_date) params.set("from_date", filters.from_date);
  if (filters.to_date) params.set("to_date", filters.to_date);
  if (filters.region_id) params.set("region_id", String(filters.region_id));
  if (filters.region) params.set("region", filters.region);
  if (filters.employee) params.set("employee", filters.employee);
  if (filters.car_id) params.set("car_id", String(filters.car_id));
  if (filters.car_state_number) {
    params.set("car_state_number", filters.car_state_number);
  }
  if (filters.source) params.set("source", filters.source);
  if (filters.include_excluded) params.set("include_excluded", "true");

  return apiFetchJson<SummaryOut>(
    `/api/v1/reports/summary?${params.toString()}`
  );
}

export async function getReportFilters(filters: {
  from_date?: string;
  to_date?: string;
  source?: string;
  include_excluded?: boolean;
}): Promise<ReportsFiltersOut> {
  const params = new URLSearchParams();
  if (filters.from_date) params.set("from_date", filters.from_date);
  if (filters.to_date) params.set("to_date", filters.to_date);
  if (filters.source) params.set("source", filters.source);
  if (filters.include_excluded) params.set("include_excluded", "true");

  return apiFetchJson<ReportsFiltersOut>(
    `/api/v1/reports/filters?${params.toString()}`
  );
}

export async function getFuelRecords(filters: {
  from_date?: string;
  to_date?: string;
  region_id?: number;
  region?: string;
  employee?: string;
  car_id?: number;
  car_state_number?: string;
  source?: string;
  cursor?: string;
  offset?: number;
  limit?: number;
  include_excluded?: boolean;
}): Promise<RecordsPageOut> {
  const params = new URLSearchParams();
  if (filters.from_date) params.set("from_date", filters.from_date);
  if (filters.to_date) params.set("to_date", filters.to_date);
  if (filters.region_id) params.set("region_id", String(filters.region_id));
  if (filters.region) params.set("region", filters.region);
  if (filters.employee) params.set("employee", filters.employee);
  if (filters.car_id) params.set("car_id", String(filters.car_id));
  if (filters.car_state_number) {
    params.set("car_state_number", filters.car_state_number);
  }
  if (filters.source) params.set("source", filters.source);
  if (filters.cursor) params.set("cursor", filters.cursor);
  params.set("offset", String(filters.offset ?? 0));
  params.set("limit", String(filters.limit ?? 50));
  if (filters.include_excluded) params.set("include_excluded", "true");

  return apiFetchJson<RecordsPageOut>(
    `/api/v1/reports/records?${params.toString()}`
  );
}

export async function getAccessUsers(showAll = false): Promise<AccessUserOut[]> {
  const params = new URLSearchParams({
    show_all: showAll ? "true" : "false",
  });
  return apiFetchJson<AccessUserOut[]>(
    `/api/v1/access/users?${params.toString()}`
  );
}

export async function createAccessUser(
  payload: AccessUserCreateIn
): Promise<AccessUserCreateOut> {
  return apiFetchJson<AccessUserCreateOut>("/api/v1/access/users", {
    method: "POST",
    body: payload,
  });
}

export async function updateAccessUserProfile(
  userId: number,
  payload: AccessUserProfilePatchIn
): Promise<AccessUserOut> {
  return apiFetchJson<AccessUserOut>(`/api/v1/access/users/${userId}/profile`, {
    method: "PATCH",
    body: payload,
  });
}

export async function setAccessUserStatus(
  userId: number,
  isActive: boolean
): Promise<AccessUserOut> {
  const payload: AccessStatusPatchIn = { is_active: isActive };
  return apiFetchJson<AccessUserOut>(`/api/v1/access/users/${userId}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function setAccessUserRole(
  userId: number,
  role: AccessRole
): Promise<AccessUserOut> {
  const payload: AccessRolePatchIn = { role };
  return apiFetchJson<AccessUserOut>(`/api/v1/access/users/${userId}/role`, {
    method: "PATCH",
    body: payload,
  });
}

export async function resetAccessUserPassword(
  userId: number
): Promise<AccessPasswordOut> {
  return apiFetchJson<AccessPasswordOut>(
    `/api/v1/access/users/${userId}/reset-password`,
    { method: "POST" }
  );
}

export async function updateAccessUserPassword(
  userId: number,
  payload: AccessPasswordPatchIn
): Promise<AccessPasswordOut> {
  return apiFetchJson<AccessPasswordOut>(`/api/v1/access/users/${userId}/password`, {
    method: "PATCH",
    body: payload,
  });
}

export async function setupOwnPassword(
  payload: PasswordSetupIn
): Promise<PasswordSetupOut> {
  return apiFetchJson<PasswordSetupOut>("/api/v1/auth/password/setup", {
    method: "POST",
    body: payload,
  });
}

export async function getAccessEvents(limit = 100): Promise<AccessLogOut[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiFetchJson<AccessLogOut[]>(
    `/api/v1/reports/access-events?${params.toString()}`
  );
}

export async function getAccessRegions(): Promise<RegionOut[]> {
  return apiFetchJson<RegionOut[]>("/api/v1/access/regions");
}

