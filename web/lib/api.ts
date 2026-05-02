import type {
  ActionReceipt,
  AdminChannel,
  ApprovalRecord,
  B2AnalyticsOptions,
  B2CollectResult,
  B2ContentCatalogItem,
  B2RightsHolder,
  ChannelVideo,
  ExecutionMode,
  IntegrationRun,
  IntegrationTaskSpec,
  LeadDiscoveryResult,
  MetabaseReport,
  MyChannel,
  PendingItem,
  Platform,
  ResourceSummary,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001/dashboard";
const RPA_BASE = API_BASE.replace(/\/dashboard$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
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

export const fetchMyChannels = (): Promise<{ items: MyChannel[] }> => request("/api/channels/me");
export const fetchChannelVideos = (): Promise<ChannelVideo[]> => request<{ items: ChannelVideo[] }>("/api/channels/me/videos").then((res) => res.items);
export const applyCreator = (channelId: string, platform: Extract<Platform, "kakao" | "naver">): Promise<ActionReceipt> =>
  request("/api/channels/me/creator-applications", { method: "POST", body: JSON.stringify({ channel_id: channelId, platform }) });
export const requestVideoUsage = (videoId: string): Promise<ActionReceipt> =>
  request(`/api/channels/me/videos/${videoId}/usage-requests`, { method: "POST", body: JSON.stringify({ video_id: videoId }) });
export const requestRelief = (videoId: string): Promise<ActionReceipt> =>
  request(`/api/channels/me/videos/${videoId}/relief-requests`, { method: "POST", body: JSON.stringify({ video_id: videoId }) });

export const fetchAdminOverview = (): Promise<{ pending: PendingItem[] }> => request("/api/admin/overview");
export const fetchAdminChannels = (): Promise<{ items: AdminChannel[] }> => request("/api/admin/channels");
export const fetchAdminVideos = (): Promise<{ items: ChannelVideo[] }> => request("/api/admin/videos");
export const registerAdminVideo = (payload: { title: string; rights_holder_name: string; registered_by?: string }): Promise<ActionReceipt> =>
  request("/api/admin/videos", { method: "POST", body: JSON.stringify(payload) });
export const runLeadDiscovery = (videoId: string): Promise<LeadDiscoveryResult> =>
  request("/api/admin/lead-discovery", { method: "POST", body: JSON.stringify({ video_id: videoId }) });
export const fetchLeadDiscovery = (runId: string): Promise<LeadDiscoveryResult> => request(`/api/admin/lead-discovery/${runId}`);
export const fetchMetabaseReport = (): Promise<MetabaseReport> => request("/api/admin/reports/metabase");
export const fetchResources = (): Promise<ResourceSummary> => request("/api/integration/resources");

async function rpaRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${RPA_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const fetchPendingApprovals = (): Promise<ApprovalRecord[]> => rpaRequest("/api/approvals/pending");
export const approveRun = (approvalId: string, decidedBy = "admin", note = ""): Promise<{ approval_id: string; execution_result: Record<string, unknown> }> =>
  rpaRequest(`/api/approvals/${approvalId}/approve`, { method: "POST", body: JSON.stringify({ decided_by: decidedBy, note }) });
export const rejectRun = (approvalId: string, decidedBy = "admin", note = ""): Promise<{ approval_id: string; status: string }> =>
  rpaRequest(`/api/approvals/${approvalId}/reject`, { method: "POST", body: JSON.stringify({ decided_by: decidedBy, note }) });
export const fetchB2ContentCatalog = (): Promise<B2ContentCatalogItem[]> => rpaRequest("/api/admin/b2/content-catalog");
export const fetchB2RightsHolders = (): Promise<B2RightsHolder[]> => rpaRequest("/api/admin/b2/rights-holders?enabled_only=false");
export const fetchB2AnalyticsOptions = (): Promise<B2AnalyticsOptions> => rpaRequest("/api/admin/b2/analytics/options");
export const collectB2SupabaseReports = (payload: { triggered_by?: string; max_clips_per_identifier: number }): Promise<B2CollectResult> =>
  rpaRequest("/api/admin/b2/supabase/collect", { method: "POST", body: JSON.stringify(payload) });
