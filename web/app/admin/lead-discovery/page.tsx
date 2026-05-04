"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// ── 타입 ──────────────────────────────────────────────────────────────────────
interface Lead {
  id: string;
  channel_id: string;
  channel_name: string;
  channel_url: string;
  platform: string;
  genre: string;
  grade: string | null;
  monthly_views: number;
  subscriber_count: number | null;
  email: string | null;
  email_status: string;
  review_status: "pending" | "promoted" | "blocked";
  block_reason: string | null;
  reviewed_at: string | null;
  discovered_at: string;
}

type ReviewStatus = "pending" | "promoted" | "blocked" | "all";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── API 훅 ────────────────────────────────────────────────────────────────────
function useLeads(reviewStatus: ReviewStatus, grade: string) {
  return useQuery<Lead[]>({
    queryKey: ["leads", reviewStatus, grade],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (reviewStatus !== "all") params.set("review_status", reviewStatus);
      if (grade) params.set("grade", grade);
      const res = await fetch(`${API_BASE}/api/admin/leads?${params}`);
      if (!res.ok) throw new Error("리드 목록 조회 실패");
      const data = await res.json();
      return data.items ?? [];
    },
    staleTime: 30_000,
  });
}

function usePromote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, note }: { id: string; note?: string }) => {
      const res = await fetch(`${API_BASE}/api/admin/leads/${encodeURIComponent(id)}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "승격 실패");
      }
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}

function useBlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
      const res = await fetch(`${API_BASE}/api/admin/leads/${encodeURIComponent(id)}/block`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "차단 실패");
      }
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}

function useUnblock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${API_BASE}/api/admin/leads/${encodeURIComponent(id)}/block`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("차단 해제 실패");
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}

function useRunC1() {
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/api/c1/trigger`, { method: "POST" });
      if (!res.ok) throw new Error("C-1 실행 실패");
      return res.json();
    },
  });
}

// ── 유틸 ──────────────────────────────────────────────────────────────────────
const GRADE_COLOR: Record<string, string> = {
  A: "bg-yellow-100 text-yellow-800",
  B: "bg-blue-100 text-blue-800",
  "B?": "bg-purple-100 text-purple-700",
  C: "bg-gray-100 text-gray-600",
};

function fmtViews(n: number) {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(0)}만`;
  return n.toLocaleString();
}

function fmtSubs(n: number | null) {
  if (!n) return "-";
  if (n >= 10_000) return `${(n / 10_000).toFixed(1)}만`;
  return n.toLocaleString();
}

// ── BlockModal ────────────────────────────────────────────────────────────────
function BlockModal({
  lead,
  onConfirm,
  onCancel,
  loading,
}: {
  lead: Lead;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-1">채널 차단</h3>
        <p className="text-sm text-gray-500 mb-4">
          <span className="font-medium text-gray-700">{lead.channel_name}</span>
          을(를) 차단하면 이후 C-1 발굴에서 제외됩니다.
        </p>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          차단 사유 <span className="text-red-400">*</span>
        </label>
        <textarea
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
          rows={3}
          placeholder="예: 방송사 공식 채널, 클립 위주 아닌 예능 채널 등"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <div className="flex gap-2 mt-4 justify-end">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
          >
            취소
          </button>
          <button
            onClick={() => reason.trim() && onConfirm(reason.trim())}
            disabled={loading || !reason.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-red-500 text-white font-medium hover:bg-red-600 disabled:opacity-50"
          >
            {loading ? "처리 중…" : "차단 확인"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────
export default function LeadDiscoveryPage() {
  const [tab, setTab] = useState<ReviewStatus>("pending");
  const [grade, setGrade] = useState("");
  const [blockTarget, setBlockTarget] = useState<Lead | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);

  const { data: leads = [], isLoading, error } = useLeads(tab, grade);
  const promote = usePromote();
  const block = useBlock();
  const unblock = useUnblock();
  const runC1 = useRunC1();

  const showToast = (msg: string, type: "ok" | "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handlePromote = async (lead: Lead) => {
    try {
      await promote.mutateAsync({ id: lead.channel_id });
      showToast(`${lead.channel_name} → 시드 채널 승격 완료`, "ok");
    } catch (e: any) {
      showToast(e.message, "err");
    }
  };

  const handleBlock = async (reason: string) => {
    if (!blockTarget) return;
    try {
      await block.mutateAsync({ id: blockTarget.channel_id, reason });
      showToast(`${blockTarget.channel_name} 차단 완료`, "ok");
      setBlockTarget(null);
    } catch (e: any) {
      showToast(e.message, "err");
    }
  };

  const handleUnblock = async (lead: Lead) => {
    try {
      await unblock.mutateAsync(lead.channel_id);
      showToast(`${lead.channel_name} 차단 해제`, "ok");
    } catch (e: any) {
      showToast(e.message, "err");
    }
  };

  const handleRunC1 = async () => {
    try {
      showToast("C-1 리드 발굴 실행 중…", "ok");
      await runC1.mutateAsync();
      showToast("C-1 실행 완료. 목록을 새로고침하세요.", "ok");
    } catch (e: any) {
      showToast(e.message, "err");
    }
  };

  const TABS: { key: ReviewStatus; label: string }[] = [
    { key: "pending", label: "검토 대기" },
    { key: "promoted", label: "시드 승격" },
    { key: "blocked", label: "차단됨" },
    { key: "all", label: "전체" },
  ];

  return (
    <div className="p-8">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">리드 채널 발굴</h1>
          <p className="text-sm text-gray-400 mt-1">
            발굴된 채널을 검토하여 시드 채널로 승격하거나 차단합니다.
          </p>
        </div>
        <button
          onClick={handleRunC1}
          disabled={runC1.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 disabled:opacity-50"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {runC1.isPending ? "실행 중…" : "리드 발굴 실행"}
        </button>
      </div>

      {/* 필터 영역 */}
      <div className="flex items-center justify-between mb-4 gap-4">
        {/* 탭 */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-1.5 text-sm rounded-md font-medium transition-colors ${
                tab === key
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 등급 필터 */}
        <select
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-teal-400"
        >
          <option value="">전체 등급</option>
          <option value="A">A 등급</option>
          <option value="B">B 등급</option>
          <option value="B?">B? 등급</option>
          <option value="C">C 등급</option>
        </select>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">채널</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">등급</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">월간 숏츠 조회</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">구독자</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">발굴일</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">상태</th>
              <th className="px-5 py-3.5 text-right text-xs text-gray-500 font-semibold uppercase tracking-wide">액션</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-gray-400">
                  불러오는 중…
                </td>
              </tr>
            )}
            {!isLoading && error && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-red-400">
                  오류: {(error as Error).message}
                </td>
              </tr>
            )}
            {!isLoading && !error && leads.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-gray-400">
                  해당하는 채널이 없습니다.
                </td>
              </tr>
            )}
            {leads.map((lead) => (
              <tr key={lead.id} className="border-b border-gray-50 hover:bg-gray-50/60 transition-colors">
                {/* 채널 */}
                <td className="px-5 py-4">
                  <div className="flex flex-col gap-0.5">
                    <a
                      href={lead.channel_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-gray-900 hover:text-teal-600 hover:underline"
                    >
                      {lead.channel_name}
                    </a>
                    <span className="text-xs text-gray-400">{lead.genre}</span>
                  </div>
                </td>
                {/* 등급 */}
                <td className="px-5 py-4">
                  <span
                    className={`inline-block px-2.5 py-0.5 text-xs font-bold rounded-full ${
                      GRADE_COLOR[lead.grade ?? "C"] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {lead.grade ?? "-"}
                  </span>
                </td>
                {/* 월간 조회 */}
                <td className="px-5 py-4 text-sm text-gray-700 tabular-nums">
                  {fmtViews(lead.monthly_views)}
                </td>
                {/* 구독자 */}
                <td className="px-5 py-4 text-sm text-gray-700 tabular-nums">
                  {fmtSubs(lead.subscriber_count)}
                </td>
                {/* 발굴일 */}
                <td className="px-5 py-4 text-sm text-gray-500">
                  {lead.discovered_at?.slice(0, 10) ?? "-"}
                </td>
                {/* 상태 */}
                <td className="px-5 py-4">
                  {lead.review_status === "promoted" && (
                    <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-teal-100 text-teal-700">
                      시드 승격
                    </span>
                  )}
                  {lead.review_status === "blocked" && (
                    <div className="flex flex-col gap-0.5">
                      <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-600 w-fit">
                        차단됨
                      </span>
                      {lead.block_reason && (
                        <span className="text-xs text-gray-400 max-w-[140px] truncate" title={lead.block_reason}>
                          {lead.block_reason}
                        </span>
                      )}
                    </div>
                  )}
                  {lead.review_status === "pending" && (
                    <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-100 text-amber-700">
                      검토 대기
                    </span>
                  )}
                </td>
                {/* 액션 */}
                <td className="px-5 py-4">
                  <div className="flex items-center justify-end gap-2">
                    {lead.review_status === "pending" && (
                      <>
                        <button
                          onClick={() => handlePromote(lead)}
                          disabled={promote.isPending}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-50"
                        >
                          시드 승격
                        </button>
                        <button
                          onClick={() => setBlockTarget(lead)}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-red-200 text-red-500 hover:bg-red-50"
                        >
                          차단
                        </button>
                      </>
                    )}
                    {lead.review_status === "blocked" && (
                      <button
                        onClick={() => handleUnblock(lead)}
                        disabled={unblock.isPending}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        차단 해제
                      </button>
                    )}
                    {lead.review_status === "promoted" && (
                      <span className="text-xs text-gray-300">-</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* BlockModal */}
      {blockTarget && (
        <BlockModal
          lead={blockTarget}
          onConfirm={handleBlock}
          onCancel={() => setBlockTarget(null)}
          loading={block.isPending}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium transition-all ${
            toast.type === "ok"
              ? "bg-gray-900 text-white"
              : "bg-red-500 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
