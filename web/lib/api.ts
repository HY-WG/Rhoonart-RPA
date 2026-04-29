import type {
  IntegrationTaskSpec,
  IntegrationRun,
  ChannelVideo,
  ResourceSummary,
  ExecutionMode,
  ApprovalRecord,
} from "./types";

// Python FastAPI 백엔드 URL — 개발: localhost:8001, 운영: 환경변수로 교체
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001/dashboard";

// 승인 API는 /dashboard 하위가 아닌 rpa_server 루트에 마운트됨
const RPA_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001/dashboard")
  .replace(/\/dashboard$/, "");

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

// ── 태스크 ────────────────────────────────────────────────────────
export const fetchTasks = (): Promise<IntegrationTaskSpec[]> =>
  request("/api/integration/tasks");

// ── 런 ───────────────────────────────────────────────────────────
export const fetchRuns = (limit = 30): Promise<IntegrationRun[]> =>
  request(`/api/integration/runs?limit=${limit}`);

export const fetchRun = (runId: string): Promise<IntegrationRun> =>
  request(`/api/integration/runs/${runId}`);

export const startRun = (
  taskId: string,
  payload: Record<string, unknown>,
  executionMode: ExecutionMode,
  approved: boolean
): Promise<IntegrationRun> =>
  request(`/api/integration/tasks/${taskId}/run`, {
    method: "POST",
    body: JSON.stringify({ payload, execution_mode: executionMode, approved }),
  });

// ── 채널 영상 ─────────────────────────────────────────────────────
export const fetchChannelVideos = (): Promise<ChannelVideo[]> =>
  request("/api/channels/me/videos");

// ── 리소스 ───────────────────────────────────────────────────────
export const fetchResources = (): Promise<ResourceSummary> =>
  request("/api/integration/resources");

// ── 승인 (rpa_server /api/approvals) ─────────────────────────────

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

export const fetchPendingApprovals = (): Promise<ApprovalRecord[]> =>
  rpaRequest("/api/approvals/pending");

export const approveRun = (
  approvalId: string,
  decidedBy = "admin",
  note = ""
): Promise<{ approval_id: string; execution_result: Record<string, unknown> }> =>
  rpaRequest(`/api/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy, note }),
  });

export const rejectRun = (
  approvalId: string,
  decidedBy = "admin",
  note = ""
): Promise<{ approval_id: string; status: string }> =>
  rpaRequest(`/api/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy, note }),
  });
