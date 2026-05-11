import type {
  A3Applicant,
  A3ApplicantCreate,
  ActionReceipt,
  ApprovalRecord,
  NaverAnalyticsOptions,
  NaverContentCatalogCreate,
  NaverCollectResult,
  NaverCollectJob,
  NaverContentCatalogItem,
  NaverMonthlyReportConfig,
  NaverReportSchedulesResponse,
  NaverReportSchedule,
  NaverReportScheduleUpdate,
  NaverRightsHolder,
  ChannelVideo,
  ExecutionMode,
  IntegrationRun,
  IntegrationTaskSpec,
  MetabaseReport,
  MetabaseReportSendResult,
  MyChannel,
  OpsA3Report,
  OpsB2Report,
  OpsLeadSummary,
  PendingItem,
  Platform,
  ResourceSummary,
  WorkRequest,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001/dashboard";
const RPA_BASE = API_BASE.replace(/\/dashboard$/, "");
const RPA_TOKEN = process.env.NEXT_PUBLIC_RPA_TOKEN ?? "";
// 포털 사용자 이메일 — 향후 실제 인증으로 교체
const PORTAL_USER_EMAIL = process.env.NEXT_PUBLIC_PORTAL_USER_EMAIL ?? "hoyoungy2@gmail.com";
const NAVER_RIGHTS_HOLDERS_CACHE_KEY = "rhoonart:naver-rights-holders:v1";

const DEFAULT_NAVER_RIGHTS_HOLDERS: NaverRightsHolder[] = [
  { rights_holder_name: "CJ" },
  { rights_holder_name: "MBC" },
  { rights_holder_name: "바른손이앤에이" },
  { rights_holder_name: "웨이브" },
  { rights_holder_name: "이놀미디어" },
  { rights_holder_name: "쿠팡플레이" },
  { rights_holder_name: "쿠팡플레이(콘텐츠마이닝)" },
  { rights_holder_name: "티빙" },
  { rights_holder_name: "판씨네마" },
  { rights_holder_name: "픽시엄" },
];

export interface CopyrightClaimItem {
  id: string;
  channel_id: string;
  channel_name: string;
  work_id: string;
  work_title: string;
  right_holder_id: string;
  right_holder_name: string;
  requested_at?: string | null;
  due?: string | null;
  completed?: boolean;
  status_label?: string;
  official_document_status?: "not_requested" | "requested" | "received" | string;
  official_document_status_label?: string;
  has_official_document?: boolean;
  has_admin_official_document?: boolean;
  official_document_file_path?: string | null;
  official_document_file_name?: string | null;
  official_document_uploaded_at?: string | null;
}

export interface CopyrightClaimGroup {
  right_holder_id: string;
  right_holder_name: string;
  has_previous_claim: boolean;
  claims: CopyrightClaimItem[];
}

export interface CopyrightClaimsResponse {
  items: CopyrightClaimItem[];
  groups: CopyrightClaimGroup[];
  fallback?: boolean;
}

export interface OfficialDocumentHolder {
  right_holder_id: string;
  right_holder_name: string;
  has_document: boolean;
  updated_at?: string | null;
  works?: OfficialDocumentWork[];
}

export interface OfficialDocumentWork {
  work_id: string;
  work_title: string;
  has_document: boolean;
  updated_at?: string | null;
}

export interface OfficialDocument {
  id?: string;
  right_holder_id: string;
  right_holder_name: string;
  content_body: {
    title?: string;
    body?: string;
  };
  work_id?: string | null;
  work_title?: string | null;
  created_at?: string;
  updated_at?: string;
  fallback?: boolean;
}

function normalizeNaverRightsHolders(items: NaverRightsHolder[]): NaverRightsHolder[] {
  const byName = new Map<string, NaverRightsHolder>();
  for (const item of items) {
    const name = item.rights_holder_name?.trim();
    if (!name || byName.has(name)) continue;
    byName.set(name, { ...item, rights_holder_name: name });
  }
  return [...byName.values()].sort((a, b) =>
    a.rights_holder_name.localeCompare(b.rights_holder_name, "ko")
  );
}

function readCachedNaverRightsHolders(): NaverRightsHolder[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(NAVER_RIGHTS_HOLDERS_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as { items?: NaverRightsHolder[] };
    return normalizeNaverRightsHolders(parsed.items ?? []);
  } catch {
    return [];
  }
}

function writeCachedNaverRightsHolders(items: NaverRightsHolder[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      NAVER_RIGHTS_HOLDERS_CACHE_KEY,
      JSON.stringify({ cached_at: new Date().toISOString(), items })
    );
  } catch {
    // localStorage can be unavailable in private browsing or strict browser settings.
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (error) {
    throw new Error(
      `Failed to fetch: ${API_BASE}${path} 에 연결할 수 없습니다. 프론트 NEXT_PUBLIC_API_BASE 또는 백엔드 서버 실행 상태를 확인하세요. (${(error as Error).message})`
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const fetchTasks = (): Promise<IntegrationTaskSpec[]> => request("/api/integration/tasks");
export const fetchRuns = (limit = 30): Promise<IntegrationRun[]> => request(`/api/integration/runs?limit=${limit}`);
export const fetchRun = (runId: string): Promise<IntegrationRun> => request(`/api/integration/runs/${runId}`);
export const startRun = (taskId: string, payload: Record<string, unknown>, executionMode: ExecutionMode, approved: boolean): Promise<IntegrationRun> =>
  request(`/api/integration/tasks/${taskId}/run`, { method: "POST", body: JSON.stringify({ payload, execution_mode: executionMode, approved }) });

export const fetchMyChannels = (): Promise<{ items: MyChannel[] }> => portalRequest("/api/channels/me");
export const fetchChannelVideos = (): Promise<ChannelVideo[]> => portalRequest<{ items: ChannelVideo[] }>("/api/channels/me/videos").then((res) => res.items);
export const applyCreator = (channelId: string, platform: Extract<Platform, "kakao" | "naver">): Promise<ActionReceipt> =>
  portalRequest("/api/channels/me/creator-applications", { method: "POST", body: JSON.stringify({ channel_id: channelId, platform }) });
export const requestVideoUsage = (video: ChannelVideo): Promise<ActionReceipt> =>
  portalRequest(`/api/channels/me/videos/${video.video_id}/usage-requests`, {
    method: "POST",
    body: JSON.stringify({
      video_id: video.video_id,
      channel_name: video.channel_name,
      contact_email: video.contact_email,
      work_title: video.title,
      rights_holder_name: video.rights_holder_name,
      platform: video.platform,
    }),
  });
export const fetchMyWorkRequests = (): Promise<{ items: WorkRequest[] }> =>
  portalRequest("/api/channels/me/usage-requests");
export const requestRelief = (video: ChannelVideo): Promise<ActionReceipt> =>
  portalRequest(`/api/channels/me/videos/${video.video_id}/relief-requests`, {
    method: "POST",
    body: JSON.stringify({
      video_id: video.video_id,
      channel_name: video.channel_name,
      contact_email: video.contact_email,
      work_title: video.title,
      rights_holder_name: video.rights_holder_name,
      platform: video.platform,
    }),
  });
export const createNaverRevenueSettlement = (payload: {
  name: string;
  channel_name: string;
  revenue_month: string;
  monthly_revenue: string;
  screenshot?: File | null;
}): Promise<{ status: string; item: unknown }> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("channel_name", payload.channel_name);
  formData.append("revenue_month", payload.revenue_month);
  formData.append("monthly_revenue", payload.monthly_revenue);
  if (payload.screenshot) formData.append("screenshot", payload.screenshot);
  return portalRequest("/api/channels/me/naver-revenue-settlements", {
    method: "POST",
    body: formData,
    headers: {},
  });
};

export const fetchAdminOverview = (): Promise<{ pending: PendingItem[] }> => rpaRequest("/api/admin/overview");
export const fetchAdminChannels = (): Promise<{ items: AdminChannel[] }> => request("/api/admin/channels");
export const fetchAdminVideos = (): Promise<{ items: ChannelVideo[] }> => request("/api/admin/videos");
export const registerAdminVideo = (payload: { title: string; rights_holder_name: string; registered_by?: string }): Promise<ActionReceipt> =>
  request("/api/admin/videos", { method: "POST", body: JSON.stringify(payload) });
export const runLeadDiscovery = (videoId: string): Promise<LeadDiscoveryResult> =>
  request("/api/admin/lead-discovery", { method: "POST", body: JSON.stringify({ video_id: videoId }) });
export const fetchLeadDiscovery = (runId: string): Promise<LeadDiscoveryResult> => request(`/api/admin/lead-discovery/${runId}`);
export const fetchMetabaseReport = (): Promise<MetabaseReport> => rpaRequest("/api/admin/reports/metabase");
export const sendMetabaseReport = (rightsHolderName: string): Promise<MetabaseReportSendResult> =>
  rpaRequest("/api/admin/reports/metabase/send", {
    method: "POST",
    body: JSON.stringify({ rights_holder_name: rightsHolderName }),
  });
export const fetchLatestNaverSupabaseCollectJob = (): Promise<NaverCollectJob> =>
  rpaRequest("/api/admin/naver/supabase/collect-jobs/latest");
export const fetchNaverReportSchedules = (): Promise<NaverReportSchedulesResponse> =>
  rpaRequest("/api/admin/reports/naver/schedules");
export const updateNaverReportSchedule = (
  scheduleId: number,
  payload: NaverReportScheduleUpdate
): Promise<NaverReportSchedule> =>
  rpaRequest(`/api/admin/reports/naver/schedules/${scheduleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
export const fetchOpsB2Report = (): Promise<OpsB2Report> => request("/api/admin/ops/b2-report");
export const fetchOpsA3Report = (): Promise<OpsA3Report> => request("/api/admin/ops/a3-report");
export const fetchOpsLeadSummary = (): Promise<OpsLeadSummary> => request("/api/admin/ops/lead-summary");
export const fetchResources = (): Promise<ResourceSummary> => request("/api/integration/resources");

export const approveWorkRequest = (
  requestId: string | number,
  note = "",
): Promise<{ status: string; item: WorkRequest; message: string }> =>
  rpaRequest(`/api/admin/work-requests/${encodeURIComponent(String(requestId))}/approve`, {
    method: "POST",
    body: JSON.stringify({ decided_by: "admin", note }),
  });

export const rejectWorkRequest = (
  requestId: string | number,
  note = "",
): Promise<{ status: string; item: WorkRequest; message: string }> =>
  rpaRequest(`/api/admin/work-requests/${encodeURIComponent(String(requestId))}/reject`, {
    method: "POST",
    body: JSON.stringify({ decided_by: "admin", note }),
  });

export const fetchCopyrightClaims = (): Promise<CopyrightClaimsResponse> =>
  rpaRequest("/api/admin/copyright-claims");

export const requestCopyrightClaim = (
  rightHolderId: string,
  workId?: string
): Promise<{
  right_holder_id: string;
  right_holder_name?: string;
  action: "no_admin_document" | "partner_request_sent" | "redirect_document" | "execute_claim";
  message: string;
  redirect_to?: string;
}> =>
  rpaRequest(`/api/admin/copyright-claims/right-holders/${encodeURIComponent(rightHolderId)}/request`, {
    method: "POST",
    body: JSON.stringify({ work_id: workId }),
  });

export const fetchOfficialDocumentHolders = (): Promise<{
  items: OfficialDocumentHolder[];
  fallback?: boolean;
}> => rpaRequest("/api/admin/official-documents");

export const fetchOfficialDocument = (rightHolderId: string, workId?: string): Promise<OfficialDocument> => {
  const suffix = workId ? `?work_id=${encodeURIComponent(workId)}` : "";
  return rpaRequest(`/api/admin/official-documents/${encodeURIComponent(rightHolderId)}${suffix}`);
};

export const saveOfficialDocument = (
  rightHolderId: string,
  contentBody: OfficialDocument["content_body"],
  workId?: string
): Promise<{ status: string; item: unknown }> =>
  rpaRequest(`/api/admin/official-documents/${encodeURIComponent(rightHolderId)}`, {
    method: "PUT",
    body: JSON.stringify({ content_body: contentBody, work_id: workId }),
  });

export const fetchPartnerCopyrightClaims = (): Promise<CopyrightClaimsResponse> =>
  rpaRequest("/api/partner/copyright-claims");

export const fetchPartnerOfficialDocument = (rightHolderId: string, workId?: string): Promise<OfficialDocument> => {
  const suffix = workId ? `?work_id=${encodeURIComponent(workId)}` : "";
  return rpaRequest(`/api/partner/official-documents/${encodeURIComponent(rightHolderId)}${suffix}`);
};

export const uploadPartnerOfficialDocumentFile = (
  claimIds: string[],
  file: File
): Promise<{ status: string; file_name: string; file_size: number; items: unknown[] }> => {
  const formData = new FormData();
  formData.append("claim_ids", JSON.stringify(claimIds));
  formData.append("file", file);
  return rpaRequest("/api/partner/copyright-claims/official-document-upload", {
    method: "POST",
    body: formData,
    headers: {},
  });
};

export const downloadClaimOfficialDocumentUrl = (claimId: string): string =>
  `${RPA_BASE}/api/admin/copyright-claims/${encodeURIComponent(claimId)}/official-document-file`;

export const sendChannelClaimEmail = (
  channelId: string,
  claimIds: string[]
): Promise<{ status: string; message: string }> =>
  rpaRequest(`/api/admin/copyright-claims/channels/${encodeURIComponent(channelId)}/send-email`, {
    method: "POST",
    body: JSON.stringify({ claim_ids: claimIds }),
  });

async function rpaRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${RPA_BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(RPA_TOKEN ? { "X-RPA-Token": RPA_TOKEN } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new Error(
      `Failed to fetch: ${RPA_BASE}${path} 에 연결할 수 없습니다. FastAPI 서버(8001), CORS, NEXT_PUBLIC_API_BASE 값을 확인하세요. (${(error as Error).message})`
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** 포털 전용 요청 — X-Portal-User 헤더를 자동으로 추가한다. */
async function portalRequest<T>(path: string, init?: RequestInit): Promise<T> {
  return rpaRequest<T>(path, {
    ...init,
    headers: {
      "X-Portal-User": PORTAL_USER_EMAIL,
      ...(init?.headers ?? {}),
    },
  });
}

export const fetchPendingApprovals = (): Promise<ApprovalRecord[]> => rpaRequest("/api/approvals/pending");
export const approveRun = (approvalId: string, decidedBy = "admin", note = ""): Promise<{ approval_id: string; execution_result: Record<string, unknown> }> =>
  rpaRequest(`/api/approvals/${approvalId}/approve`, { method: "POST", body: JSON.stringify({ decided_by: decidedBy, note }) });
export const rejectRun = (approvalId: string, decidedBy = "admin", note = ""): Promise<{ approval_id: string; status: string }> =>
  rpaRequest(`/api/approvals/${approvalId}/reject`, { method: "POST", body: JSON.stringify({ decided_by: decidedBy, note }) });
export const fetchNaverContentCatalog = (): Promise<NaverContentCatalogItem[]> => rpaRequest("/api/admin/naver/content-catalog");
export const createNaverContentCatalogItem = (
  payload: NaverContentCatalogCreate
): Promise<NaverContentCatalogItem> =>
  rpaRequest("/api/admin/naver/content-catalog", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const updateNaverWorkReportEnabled = (
  workId: number,
  naverReportEnabled: boolean
): Promise<NaverContentCatalogItem> =>
  rpaRequest(`/api/admin/naver/content-catalog/${workId}/report-enabled`, {
    method: "PATCH",
    body: JSON.stringify({ naver_report_enabled: naverReportEnabled }),
  });
export const fetchNaverRightsHolders = async (): Promise<NaverRightsHolder[]> => {
  try {
    const items = normalizeNaverRightsHolders(
      await rpaRequest<NaverRightsHolder[]>("/api/admin/naver/rights-holders?enabled_only=false")
    );
    if (items.length > 0) {
      writeCachedNaverRightsHolders(items);
      return items;
    }
  } catch (error) {
    const cached = readCachedNaverRightsHolders();
    if (cached.length > 0) return cached;
    console.warn("Using bundled naver rights holders because API lookup failed.", error);
  }
  return normalizeNaverRightsHolders(DEFAULT_NAVER_RIGHTS_HOLDERS);
};
export const fetchNaverAnalyticsOptions = (): Promise<NaverAnalyticsOptions> => rpaRequest("/api/admin/naver/analytics/options");
export const collectNaverSupabaseReports = (payload: { triggered_by?: string; max_clips_per_identifier: number }): Promise<NaverCollectResult> =>
  rpaRequest("/api/admin/naver/supabase/collect", { method: "POST", body: JSON.stringify(payload) });
export const startNaverSupabaseCollectJob = (payload: { triggered_by?: string; max_clips_per_identifier: number }): Promise<NaverCollectJob> =>
  rpaRequest("/api/admin/naver/supabase/collect-jobs", { method: "POST", body: JSON.stringify(payload) });
export const fetchNaverSupabaseCollectJob = (jobId: string): Promise<NaverCollectJob> =>
  rpaRequest(`/api/admin/naver/supabase/collect-jobs/${jobId}`);

// ── Lead Discovery ───────────────────────────────────────────────────────────
export const fetchLeads = (reviewStatus = "pending", grade = ""): Promise<{ items: unknown[]; total: number }> => {
  const params = new URLSearchParams();
  if (reviewStatus !== "all") params.set("review_status", reviewStatus);
  if (grade) params.set("grade", grade);
  return rpaRequest(`/api/admin/leads?${params}`);
};
export const promoteLead = (channelId: string, promotedBy = "admin"): Promise<unknown> =>
  rpaRequest(`/api/admin/leads/${encodeURIComponent(channelId)}/promote`, {
    method: "POST",
    body: JSON.stringify({ promoted_by: promotedBy }),
  });
export const blockLead = (channelId: string, reason: string, blockedBy = "admin"): Promise<unknown> =>
  rpaRequest(`/api/admin/leads/${encodeURIComponent(channelId)}/block`, {
    method: "POST",
    body: JSON.stringify({ reason, blocked_by: blockedBy }),
  });
export const unblockLead = (channelId: string): Promise<unknown> =>
  rpaRequest(`/api/admin/leads/${encodeURIComponent(channelId)}/block`, { method: "DELETE" });
export const triggerC1 = (): Promise<{ status: string; message?: string }> =>
  rpaRequest("/api/c1/trigger", { method: "POST", body: JSON.stringify({ payload: {} }) });
export const refreshLeadSubscribers = (): Promise<{
  status: string;
  total: number;
  updated: number;
  metrics?: unknown[];
  percent: number;
  last_run_at: string;
}> => rpaRequest("/api/admin/leads/refresh-subscribers", { method: "POST" });
export const fetchLeadSummary = (): Promise<{
  total: number;
  promoted: number;
  blocked: number;
  pending: number;
  last_run_at: string;
  last_discovery_run_at: string;
  discovered_count: number;
  new_lead_count: number;
  excluded_count: number;
  discovery_message: string;
  drama_titles: string[];
  detail_log: Array<{ message?: string; [key: string]: unknown }>;
  progress_percent: number;
}> => rpaRequest("/api/admin/leads/summary");

export const sendLeadEmail = (
  channelId: string,
  dryRun = false,
): Promise<{ status: string; channel_id: string; channel_name: string; email: string; dry_run: boolean; sent_at: string | null }> =>
  rpaRequest(`/api/admin/leads/${encodeURIComponent(channelId)}/send-email`, {
    method: "POST",
    body: JSON.stringify({ dry_run: dryRun, sent_by: "admin" }),
  });

export const bulkSendLeadEmails = (
  dryRun = false,
): Promise<{ status: string; total: number; sent: number; failed: number; dry_run: boolean }> =>
  rpaRequest("/api/admin/leads/bulk-send-email", {
    method: "POST",
    body: JSON.stringify({ dry_run: dryRun, sent_by: "admin" }),
  });

export const fetchB2ContentCatalog = fetchNaverContentCatalog;
export const fetchB2RightsHolders = fetchNaverRightsHolders;
export const fetchB2AnalyticsOptions = fetchNaverAnalyticsOptions;
export const collectB2SupabaseReports = collectNaverSupabaseReports;

// ── Seed Channels ────────────────────────────────────────────────────────────
export interface SeedChannel {
  id?: number;
  channel_title?: string;
  channel_id?: string;
  channel_url?: string;
  managed_by?: string;
  type?: string;
  status?: string;
  platform?: string;
  created_at?: string;
  updated_at?: string;
}
export const fetchSeedChannels = (platform?: string, status?: string): Promise<{ items: SeedChannel[] }> => {
  const params = new URLSearchParams();
  if (platform) params.set("platform", platform);
  if (status) params.set("status", status);
  const qs = params.toString();
  return rpaRequest(`/api/admin/seed-channels${qs ? `?${qs}` : ""}`);
};
export interface WorkSearchResult {
  work_id: number | string;
  work_title: string;
  display_title?: string;
  release_year?: string;
  rights_holder_name: string;
  identifier: string;
  source?: string;
  external_id?: string;
  media_type?: string;
  source_title?: string;
}

export const searchWorks = (q: string): Promise<{ items: WorkSearchResult[] }> =>
  rpaRequest(`/api/admin/works/search?q=${encodeURIComponent(q)}`);

export interface WorkEnrichResult {
  video_type?: string;   // "드라마" | "영화" | ...
  release_year?: string; // "2024"
  description?: string;
  genre?: string;
  country?: string;
  cast?: string;         // "이민호, 김지원, ..."
  director?: string;
  trailer_url?: string;  // YouTube URL
  thumbnail_url?: string;
  debug_log?: string[];
}
export const enrichWork = (
  title: string,
  options?: { source?: string; external_id?: string; debug_force_empty_sources?: string }
): Promise<WorkEnrichResult> => {
  const params = new URLSearchParams({ title });
  if (options?.source) params.set("source", options.source);
  if (options?.external_id) params.set("external_id", options.external_id);
  if (options?.debug_force_empty_sources) {
    params.set("debug_force_empty_sources", options.debug_force_empty_sources);
  }
  return rpaRequest(`/api/admin/works/enrich?${params.toString()}`);
};

// ── Kakao Creators ───────────────────────────────────────────────────────────
export interface KakaoCreator {
  id: number;
  batch_number?: string | null;
  creator_name: string;
  kakao_channel?: string;
  kakao_channel_name?: string | null;
  contact_email?: string;
  kakao_email?: string | null;
  phone_number?: string;
  onboarding_round?: string | null;
  partner_name?: string | null;
  is_active?: boolean | null;
  is_whitelisted?: boolean | null;
  is_crawled?: boolean | null;
  is_linked?: boolean | null;
  is_onboarded?: boolean | null;
  jjal_studio_id?: string | null;
  remarks?: string | null;
  operation_enabled?: string | null;
  whitelist_enabled?: string | null;
  crawling_collection?: number | null;
  account_type?: string | null;
  channel_link?: string | null;
  youtube_channel_id?: string | null;
  subscriber_count?: number | null;
  scale?: string | null;
  category?: string | null;
  sub_category?: string | null;
  account_classification?: string | null;
  sync_enabled?: string | null;
  zzalstudio_id?: string | null;
  onboarding_completed?: string | null;
  permission_status?: string | null;
  representative_sns_platform?: string | null;
  representative_sns_platform_other?: string | null;
  channel_name?: string | null;
  youtube_kakao_sync_wanted?: string | null;
  identity_or_business_file_url?: string | null;
  bankbook_file_url?: string | null;
  status: string;
  note?: string;
  onboarded_at?: string | null;
  created_at?: string;
  updated_at?: string;
}
export const fetchKakaoCreators = (): Promise<{ items: KakaoCreator[] }> =>
  rpaRequest("/api/admin/kakao-creators");

// ── A3 Naver Clip Applicants ─────────────────────────────────────────────────
export const fetchA3Applicants = (): Promise<A3Applicant[]> =>
  rpaRequest("/api/a3/applicants");
export const createA3Applicant = (payload: A3ApplicantCreate): Promise<A3Applicant> =>
  rpaRequest("/api/a3/applicants", { method: "POST", body: JSON.stringify(payload) });
export const triggerA3Report = (): Promise<{ status: string; message?: string }> => {
  return rpaRequest("/api/a3/trigger", {
    method: "POST",
    body: JSON.stringify({
      payload: {
        mode: "send",
      },
    }),
  });
};
export const fetchNaverMonthlyReportConfig = (): Promise<NaverMonthlyReportConfig> =>
  rpaRequest("/api/admin/naver/monthly-report");
export const downloadNaverMonthlyReportExcel = async (): Promise<Blob> => {
  let res: Response;
  try {
    res = await fetch(`${RPA_BASE}/api/admin/naver/monthly-report/export.xlsx`, {
      headers: {
        ...(RPA_TOKEN ? { "X-RPA-Token": RPA_TOKEN } : {}),
      },
    });
  } catch (error) {
    throw new Error(`엑셀 다운로드 요청에 실패했습니다. (${(error as Error).message})`);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.blob();
};
export const updateNaverMonthlyReportManager = (payload: {
  manager_name: string;
  manager_email: string;
}): Promise<NaverMonthlyReportConfig["manager"]> =>
  rpaRequest("/api/admin/naver/monthly-report/manager", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
