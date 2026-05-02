export type RunStatus = "queued" | "running" | "succeeded" | "failed";
export type ExecutionMode = "dry_run" | "real_run";
export type Platform = "youtube" | "kakao" | "naver";

export interface IntegrationTaskSpec {
  task_id: string;
  title: string;
  description: string;
  default_payload: Record<string, unknown>;
  targets: string[];
  trigger_mode: string;
  requires_approval: boolean;
  supports_dry_run: boolean;
  real_run_warning: string;
  sheet_links: Record<string, string>;
  tab_group: string;
}

export interface IntegrationRun {
  run_id: string;
  task_id: string;
  title: string;
  payload: Record<string, unknown>;
  status: RunStatus;
  execution_mode: ExecutionMode;
  requires_approval: boolean;
  approved: boolean;
  started_at: string;
  updated_at: string;
  finished_at: string | null;
  result: Record<string, unknown> | null;
  error: string;
  logs: string[];
}

export interface MyChannel {
  channel_id: string;
  name: string;
  registered_at: string;
  platform: Platform;
  status: string;
}

export interface ChannelVideo {
  video_id: string;
  title: string;
  description: string;
  channel_name: string;
  contact_email: string;
  rights_holder_name: string;
  platform: Platform;
  availability_status: string;
  thumbnail_emoji: string;
  registered_at: string;
  thumbnail_url: string;
  active_channel_count: number;
}

export interface AdminChannel {
  channel_id: string;
  name: string;
  platform: Platform;
  owner: string;
  registered_at: string;
  status: string;
  video_count: number;
}

export interface PendingItem {
  id: string;
  title: string;
  metric_label: string;
  count: number;
}

export interface Lead {
  lead_id: string;
  channel_name: string;
  platform: Platform;
  subscriber_count: number;
  contact_email: string;
  fit_score: number;
}

export interface LeadDiscoveryResult {
  run_id: string;
  status: string;
  video: ChannelVideo;
  leads: Lead[];
}

export interface MetabaseRightsHolderReport {
  id: string;
  name: string;
  embed_url: string;
  configured: boolean;
}

export interface MetabaseReport {
  title: string;
  embed_url: string;
  configured: boolean;
  env_key: string;
  reports: MetabaseRightsHolderReport[];
}

export interface B2ContentCatalogItem {
  id?: number;
  content_name: string;
  identifier: string;
  rights_holder_name: string;
  active_flag?: string;
  naver_report_enabled?: boolean;
}

export interface B2RightsHolder {
  id?: number;
  rights_holder_name: string;
  email?: string | null;
  current_work_title?: string | null;
  naver_report_enabled?: boolean;
  update_cycle?: string | null;
  looker_spreadsheet_url?: string | null;
  looker_studio_url?: string | null;
}

export interface B2AnalyticsSummary {
  clip_count: number;
  channel_count: number;
  work_count: number;
  rights_holder_count: number;
  total_views: number;
  max_views: number;
}

export interface B2AnalyticsOptions {
  channel_names: string[];
  work_titles: string[];
  rights_holder_names: string[];
  platforms: string[];
  checked_date_min: string | null;
  checked_date_max: string | null;
  uploaded_date_min: string | null;
  uploaded_date_max: string | null;
}

export interface B2CollectResult {
  status: string;
  triggered_by: string;
  max_clips_per_identifier: number;
  row_count: number;
  summary: B2AnalyticsSummary;
}

export interface ActionReceipt {
  request_id: string;
  status: string;
  action: string;
  message: string;
  payload: Record<string, unknown>;
}

export interface ApprovalRecord {
  approval_id: string;
  task_id: string;
  trace_id: string;
  summary: string;
  risk_level: string;
  preview: Record<string, unknown>;
  requested_at: string;
  status?: string;
  decided_at?: string | null;
  decided_by?: string;
  decision_note?: string;
  execution_result?: Record<string, unknown> | null;
}

export interface ResourceSummary {
  google_credentials_file: string;
  content_sheet_id: string;
  lead_sheet_id: string;
  log_sheet_id: string;
  sender_email: string;
  slack_error_channel: string;
  dashboard_repository: string;
  supabase_configured: boolean;
  tasks: Array<{
    task_id: string;
    title: string;
    targets: string[];
    trigger_mode: string;
    requires_approval: boolean;
    supports_dry_run: boolean;
    sheet_links: Record<string, string>;
  }>;
}
