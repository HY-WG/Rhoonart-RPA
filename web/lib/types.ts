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

export interface WorkRequest {
  id: string | number;
  work_title: string;
  channel_name?: string | null;
  creator_email?: string | null;
  status: "pending" | "approved" | "rejected" | string;
  requested_at: string;
  processed_at?: string | null;
  drive_link?: string | null;
  slack_ts?: string | null;
  decision_note?: string | null;
  decided_by?: string | null;
  rejection_message?: string | null;
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

export interface RightsHolderCardItem {
  name: string;
  schedule: string;
  status: "보고 완료" | "보고 대기중" | string;
}

export interface ReportDates {
  current: string;
  current_sent: boolean;
  next: string;
  next_sent: boolean;
}

export interface PendingItem {
  id: string;
  title: string;
  metric_label: string;
  count: number;
  href?: string;
  status?: string;
  rights_holders?: RightsHolderCardItem[];
  report_dates?: ReportDates;
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
  email?: string | null;
  mail?: string | null;
  naver_report_enabled?: boolean;
  configured: boolean;
}

export interface MetabaseReport {
  title: string;
  embed_url: string;
  configured: boolean;
  env_key: string;
  reports: MetabaseRightsHolderReport[];
}

export interface MetabaseReportSendResult {
  status: string;
  rights_holder_name: string;
  recipients: string[];
  dashboard_url: string;
  sent_at: string;
  elapsed_ms?: number;
}

export interface NaverMonthlyReportConfig {
  sheet: {
    sheet_id: string;
    gid: string;
    url: string;
    embed_url: string;
  };
  manager: {
    manager_name: string;
    manager_email: string;
    updated_at?: string;
  };
}

export interface NaverReportSchedule {
  schedule_id: number;
  enabled: boolean;
  days_of_week: number[];
  send_time: string;
  timezone: string;
  recipient_emails: string[];
  include_work_ids: number[];
  last_sent_at: string | null;
  next_run_at: string | null;
  rights_holder_id: number;
  rights_holder_name: string;
  manager_name?: string | null;
  email?: string | null;
  metabase_embed_url?: string | null;
}

export interface NaverReportWork {
  work_id: number;
  work_title: string;
  identifier: string | null;
  naver_report_enabled: boolean;
  rights_holder_id: number;
  rights_holder_name: string;
  manager_name?: string | null;
  email?: string | null;
  metabase_embed_url?: string | null;
}

export interface NaverReportDeliveryLog {
  id: number;
  run_id: string | null;
  execution_mode: string | null;
  send_notifications: boolean | null;
  status: string | null;
  result_json: Record<string, unknown> | null;
  created_at: string;
}

export interface NaverReportSchedulesResponse {
  schedules: NaverReportSchedule[];
  works: NaverReportWork[];
  logs: NaverReportDeliveryLog[];
}

export interface NaverReportScheduleUpdate {
  enabled: boolean;
  days_of_week: number[];
  send_time: string;
  timezone: string;
  recipient_emails: string[];
  include_work_ids: number[];
}

export interface NaverContentCatalogItem {
  id?: number;
  content_name: string;
  identifier: string;
  rights_holder_name: string;
  active_flag?: string;
  status?: string;
  naver_report_enabled?: boolean;
}

export interface NaverContentCatalogCreate {
  content_name: string;
  identifier: string;
  rights_holder_name: string;
  status?: string;
  naver_report_enabled: boolean;
}

export interface NaverRightsHolder {
  id?: number;
  rights_holder_name: string;
  email?: string | null;
  current_work_title?: string | null;
  naver_report_enabled?: boolean;
  update_cycle?: string | null;
  looker_spreadsheet_url?: string | null;
  looker_studio_url?: string | null;
}

export interface NaverAnalyticsSummary {
  clip_count: number;
  channel_count: number;
  work_count: number;
  rights_holder_count: number;
  total_views: number;
  max_views: number;
}

export interface NaverAnalyticsOptions {
  channel_names: string[];
  work_titles: string[];
  rights_holder_names: string[];
  platforms: string[];
  checked_date_min: string | null;
  checked_date_max: string | null;
  uploaded_date_min: string | null;
  uploaded_date_max: string | null;
}

export interface NaverCollectResult {
  status: string;
  triggered_by: string;
  max_clips_per_identifier: number;
  row_count: number;
  summary: NaverAnalyticsSummary;
}

export interface NaverCollectJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  phase: string;
  message: string;
  percent: number;
  completed: number;
  total: number;
  row_count: number;
  run_id?: string;
  triggered_by?: string;
  max_clips_per_identifier?: number;
  created_at?: string;
  updated_at?: string;
  finished_at?: string;
  error_message?: string;
  summary?: NaverAnalyticsSummary;
}

export type B2ContentCatalogItem = NaverContentCatalogItem;
export type B2RightsHolder = NaverRightsHolder;
export type B2AnalyticsSummary = NaverAnalyticsSummary;
export type B2AnalyticsOptions = NaverAnalyticsOptions;
export type B2CollectResult = NaverCollectResult;

// ── A3 Naver Clip Applicant ──────────────────────────────────────────────────
export type A3Platform =
  | "네이버 클립프로필(네이버 TV 포함)"
  | "유튜브"
  | "인스타그램"
  | "틱톡"
  | "카카오톡숏폼";

export interface A3Applicant {
  applicant_id: string;
  name: string;
  phone_number: string;
  naver_id: string;
  naver_clip_profile_name: string;
  naver_clip_profile_id: string;
  representative_channel_name: string;
  representative_channel_platform: string;
  channel_url: string;
  submitted_at: string;
}

export type A3ApplicantCreate = Omit<A3Applicant, "applicant_id" | "submitted_at">;

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

export interface OpsB2ReportRightsHolder {
  name: string;
  schedule_days: string[];
  schedule_time: string;
  report_status: "completed" | "pending";
}

export interface OpsB2Report {
  active_count: number;
  rights_holders: OpsB2ReportRightsHolder[];
}

export interface OpsReportDate {
  date: string;
  label: string;
  status: "completed" | "pending";
}

export interface OpsA3Report {
  current_month: OpsReportDate;
  next_month: OpsReportDate;
}

export interface OpsLeadSummary {
  videos_needing_leads: number;
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
