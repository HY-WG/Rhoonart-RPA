"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// ── 타입 ──────────────────────────────────────────────────────────────────────
interface WorkRequest {
  id: string;
  work_title: string;
  channel_name: string | null;
  creator_email: string | null;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  processed_at: string | null;
  drive_link: string | null;
  slack_ts: string | null;
  decision_note?: string | null;
  rejection_message?: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001/dashboard";
const RPA_BASE = API_BASE.replace(/\/dashboard$/, "").replace(/\/$/, "");
const RPA_TOKEN = process.env.NEXT_PUBLIC_RPA_TOKEN ?? "";

async function rpaRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${RPA_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(RPA_TOKEN ? { "X-RPA-Token": RPA_TOKEN } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new Error(
      `Failed to fetch: ${RPA_BASE}${path} 에 연결할 수 없습니다. FastAPI 서버(8001)와 web/.env.local 설정을 확인하세요. (${(error as Error).message})`
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── 훅 ───────────────────────────────────────────────────────────────────────
function useWorkRequests(status: string) {
  return useQuery<WorkRequest[]>({
    queryKey: ["work-requests", status],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (status !== "all") params.set("status", status);
      const data = await rpaRequest<{ items?: WorkRequest[] }>(
        `/api/admin/work-requests?${params}`
      );
      return data.items ?? [];
    },
    staleTime: 30_000,
  });
}

function useTriggerA2() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { channel_name: string; work_title: string }) => {
      return rpaRequest<{ channel_name?: string; work_title?: string }>("/api/a2/trigger", {
        method: "POST",
        body: JSON.stringify({ payload: body }),
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-requests"] }),
  });
}

function useApproveWorkRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (requestId: string) =>
      rpaRequest(`/api/admin/work-requests/${encodeURIComponent(requestId)}/approve`, {
        method: "POST",
        body: JSON.stringify({ decided_by: "admin" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-requests"] }),
  });
}

function useRejectWorkRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (requestId: string) =>
      rpaRequest<{ message?: string }>(
        `/api/admin/work-requests/${encodeURIComponent(requestId)}/reject`,
        {
          method: "POST",
          body: JSON.stringify({ decided_by: "admin" }),
        }
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-requests"] }),
  });
}

// ── 유틸 ──────────────────────────────────────────────────────────────────────
const STATUS_META = {
  pending: { label: "처리 중", cls: "bg-amber-100 text-amber-700" },
  approved: { label: "승인됨", cls: "bg-emerald-100 text-emerald-700" },
  rejected: { label: "거절됨", cls: "bg-red-100 text-red-500" },
} as const;

// ── ManualTriggerPanel ────────────────────────────────────────────────────────
function ManualTriggerPanel() {
  const [channelName, setChannelName] = useState("");
  const [workTitle, setWorkTitle] = useState("");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const trigger = useTriggerA2();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResult(null);
    try {
      const res = await trigger.mutateAsync({ channel_name: channelName.trim(), work_title: workTitle.trim() });
      setResult({
        ok: true,
        msg: `승인 완료 — ${res.channel_name ?? channelName} / ${res.work_title ?? workTitle}`,
      });
      setChannelName("");
      setWorkTitle("");
    } catch (error) {
      setResult({ ok: false, msg: (error as Error).message });
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">수동 승인 처리</h2>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">채널명 (크리에이터명)</label>
          <input
            required
            value={channelName}
            onChange={(e) => setChannelName(e.target.value)}
            placeholder="예: 정호영"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-teal-400"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">작품명</label>
          <input
            required
            value={workTitle}
            onChange={(e) => setWorkTitle(e.target.value)}
            placeholder="예: 21세기 대군부인"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-teal-400"
          />
        </div>
        <button
          type="submit"
          disabled={trigger.isPending}
          className="px-4 py-2 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 disabled:opacity-50"
        >
          {trigger.isPending ? "처리 중…" : "승인 처리"}
        </button>
      </form>
      {result && (
        <p className={`mt-3 text-sm ${result.ok ? "text-emerald-600" : "text-red-500"}`}>
          {result.ok ? "✓ " : "✗ "}{result.msg}
        </p>
      )}
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────
export default function WorkApplicationPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const { data: requests = [], isLoading, error } = useWorkRequests(statusFilter);
  const approve = useApproveWorkRequest();
  const reject = useRejectWorkRequest();

  const TABS = [
    { key: "all", label: "전체" },
    { key: "pending", label: "처리 중" },
    { key: "approved", label: "승인됨" },
    { key: "rejected", label: "거절됨" },
  ];

  return (
    <div className="p-8">
      {/* 헤더 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">작품 사용 신청 진행 현황</h1>
        <p className="text-sm text-gray-400 mt-1">
          크리에이터의 작품 사용 신청을 관리하고 수동으로 승인 처리합니다.
        </p>
      </div>

      {/* 수동 실행 */}
      <ManualTriggerPanel />

      {/* 필터 탭 */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-4 w-fit">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setStatusFilter(key)}
            className={`px-4 py-1.5 text-sm rounded-md font-medium transition-colors ${
              statusFilter === key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">작품명</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">채널 / 이메일</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">상태</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">신청일</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">처리일</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">안내</th>
              <th className="px-5 py-3.5 text-right text-xs text-gray-500 font-semibold uppercase">액션</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-gray-400">불러오는 중…</td>
              </tr>
            )}
            {!isLoading && error && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-red-400">
                  오류: {(error as Error).message}
                </td>
              </tr>
            )}
            {!isLoading && !error && requests.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-gray-400">
                  신청 내역이 없습니다.
                </td>
              </tr>
            )}
            {requests.map((req) => {
              const meta = STATUS_META[req.status] ?? STATUS_META.pending;
              return (
                <tr key={req.id} className="border-b border-gray-50 hover:bg-gray-50/60 transition-colors">
                  <td className="px-5 py-4 text-sm font-medium text-gray-900">{req.work_title}</td>
                  <td className="px-5 py-4">
                    <p className="text-sm text-gray-700">{req.channel_name ?? "-"}</p>
                    <p className="text-xs text-gray-400">{req.creator_email ?? ""}</p>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full ${meta.cls}`}>
                      {meta.label}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-sm text-gray-500">
                    {req.requested_at ? req.requested_at.slice(0, 10) : "-"}
                  </td>
                  <td className="px-5 py-4 text-sm text-gray-500">
                    {req.processed_at ? req.processed_at.slice(0, 10) : "-"}
                  </td>
                  <td className="px-5 py-4 text-xs text-gray-500">
                    {req.rejection_message ?? req.decision_note ?? "-"}
                  </td>
                  <td className="px-5 py-4 text-right">
                    {req.status === "pending" ? (
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={async () => {
                            setResult(null);
                            try {
                              await approve.mutateAsync(req.id);
                              setResult({ ok: true, msg: "승인 처리 및 메일 발송 요청 완료" });
                            } catch (err) {
                              setResult({ ok: false, msg: (err as Error).message });
                            }
                          }}
                          disabled={approve.isPending || reject.isPending}
                          className="rounded-lg bg-teal-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-600 disabled:opacity-50"
                        >
                          허용
                        </button>
                        <button
                          onClick={async () => {
                            setResult(null);
                            try {
                              const response = await reject.mutateAsync(req.id);
                              setResult({ ok: true, msg: response.message ?? "거절 처리 완료" });
                            } catch (err) {
                              setResult({ ok: false, msg: (err as Error).message });
                            }
                          }}
                          disabled={approve.isPending || reject.isPending}
                          className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-500 hover:bg-red-50 disabled:opacity-50"
                        >
                          거절
                        </button>
                      </div>
                    ) : req.drive_link ? (
                      <a href={req.drive_link} target="_blank" rel="noopener noreferrer" className="text-xs text-teal-600 hover:underline">
                        파일 열기
                      </a>
                    ) : (
                      <span className="text-xs text-gray-300">-</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {result && (
        <div className={`fixed bottom-6 right-6 rounded-xl px-5 py-3 text-sm font-medium text-white shadow-lg ${result.ok ? "bg-gray-900" : "bg-red-500"}`}>
          {result.msg}
        </div>
      )}
    </div>
  );
}
