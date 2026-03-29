export type FuelType = "GASOLINE" | "DIESEL";

export type FuelSource = "CARD" | "TGBOT" | "TRUCK";

export type AccessRole = "Заправщик" | "Менеджер" | "Администратор";

export interface UserMeOut {
  id: number;
  username: string;
  full_name: string;
  groups: string[];
  auth_provider: string;
  mfa_policy_enabled: boolean;
  must_change_password: boolean;
  telegram_linked: boolean;
  has_my_editable_fuel_records?: boolean;
  region_id: number | null;
}

export interface TelegramLinkCodeOut {
  code: string;
  expires_at: string;
  ttl_minutes: number;
  bot_link_with_start: string;
  share_message: string;
}

export interface CarOut {
  id: number;
  state_number: string;
  model: string;
  code: string;
  region_name: string | null;
}

export interface FuelRecordIn {
  car_id: number;
  liters: number;
  fuel_type: FuelType;
  source: FuelSource;
  notes: string;
}

export type FuelReportingStatus =
  | "ACTIVE"
  | "EXCLUDED_DUPLICATE"
  | "EXCLUDED_DELETION";

export interface FuelRecordOut {
  id: number;
  car_id: number;
  car_state_number: string;
  car_is_fuel_tanker: boolean;
  liters: number | string;
  fuel_type: FuelType;
  source: FuelSource;
  filled_at: string;
  employee_name: string;
  region_name: string | null;
  reporting_status?: FuelReportingStatus;
  notes?: string;
}

export interface FuelRecordPatchIn {
  car_id?: number;
  liters?: number;
  fuel_type?: FuelType;
  source?: FuelSource;
  notes?: string;
  filled_at?: string;
  reporting_status?: FuelReportingStatus;
}

export interface SummaryOut {
  total_records: number;
  total_liters: number;
  avg_liters: number;
}

export interface ReportsFiltersOut {
  employees: string[];
  regions: string[];
}

export interface RecordsPageOut<TItem extends FuelRecordOut = FuelRecordOut> {
  items: TItem[];
  total: number;
  has_next?: boolean;
  next_cursor?: string | null;
}

export interface AccessUserOut {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  is_active: boolean;
  region_id: number | null;
  region_name: string | null;
  groups: string[];
}

export interface AccessUserCreateIn {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  password?: string;
  region_id: number | null;
  activate: boolean;
}

export interface AccessUserCreateOut {
  id: number;
  username: string;
  temporary_password: string | null;
}

export interface AccessStatusPatchIn {
  is_active: boolean;
}

export interface AccessRolePatchIn {
  role: AccessRole;
}

export interface AccessPasswordOut {
  id: number;
  username: string;
  temporary_password: string | null;
}

export interface AccessPasswordPatchIn {
  password?: string;
  generate_temporary: boolean;
}

export interface PasswordSetupIn {
  password?: string;
  generate: boolean;
}

export interface PasswordSetupOut {
  must_change_password: boolean;
  generated_password: string | null;
}

export interface AccessLogOut {
  id: number;
  actor_username: string;
  action: string;
  details: string;
  created_at: string;
}

export interface AccessUserProfilePatchIn {
  email?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  region_id?: number;
}

export interface RegionOut {
  id: number;
  name: string;
}

