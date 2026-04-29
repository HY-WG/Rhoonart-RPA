// ── 공용 타입 정의 ────────────────────────────────────────────────

export type RunStatus = "queued" | "running" | "succeeded" | "failed";
export type ExecutionMode = "dry_run" | "real_run";

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

export interface ChannelVideo {
  video_id: string;
  title: string;
  description: string;
  channel_name: string;
  contact_email: string;
  rights_holder_name: string;
  platform: string;
  availability_status: string;
  thumbnail_emoji: string;
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
