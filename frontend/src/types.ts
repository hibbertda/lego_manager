// Shared API response shapes. Keep in sync with app/blueprints/api.py.

export type BuildStatus =
  | 'not_started'
  | 'in_progress'
  | 'built'
  | 'wishlist'
  | string;

export interface SessionUser {
  id: number;
  username: string;
  email: string | null;
  role: string;
  is_admin: boolean;
  auth_provider: string;
}

export interface SessionInfo {
  authenticated: boolean;
  needs_setup: boolean;
  user: SessionUser | null;
  csrf_token: string;
  brickset_configured: boolean;
  owned_set_count?: number;
  oidc_enabled: boolean;
  oidc_name: string | null;
  local_disabled: boolean;
}

export interface SetSummary {
  setID: number;
  setNumber: string;
  name: string;
  year: number | null;
  theme: string | null;
  pieces: number | null;
  build_status: BuildStatus;
  build_page: number;
  favorite: boolean;
  location: string | null;
  image: string | null;
  status_label: string;
  status_icon: string;
  status_badge_class: string;
  detail_url: string;
  label_image_url: string | null;
  has_label?: boolean;
  instructions?: string[];
  local_images?: string[];
  local_image_urls?: string[];
  local_instructions?: string[];
  local_instruction_urls?: string[];
  label_url?: string | null;
  launchDate?: string | null;
}

export interface SetListResponse {
  sets: SetSummary[];
  page: number;
  total_pages: number;
  total: number;
  themes: string[];
  locations: string[];
  sort_labels: Record<string, string>;
  build_statuses: string[];
}

export interface SetDetailResponse {
  set: SetSummary;
  locations: string[];
}

export interface SearchResponse {
  sets: SetSummary[];
  query: string;
  page: number;
  total_pages: number;
  total: number;
}

export interface SuggestResult {
  id: number;
  name: string;
  setNumber: string;
  year: number | null;
  theme: string | null;
  image: string | null;
  url: string;
}

export interface SuggestResponse {
  results: SuggestResult[];
  total: number;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  role: string;
  is_active: boolean;
  auth_provider: string;
}

export interface OidcProvider {
  name: string;
  issuer: string;
  client_id: string;
  client_secret: string;
  scopes: string;
  enabled: boolean;
  default_role: string;
  disable_local_login: boolean;
  auto_create_users: boolean;
}

export interface BricksetSettings {
  api_key: string;
  username: string;
  password: string;
}

export interface MissingMetadataResult extends SetSummary {
  missing_fields: string[];
}

export const SORT_OPTIONS_FALLBACK: Record<string, string> = {
  name_asc: 'Name (A-Z)',
};
