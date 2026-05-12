"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchLeads,
  promoteLead,
  blockLead,
  unblockLead,
  triggerC1,
  refreshLeadSubscribers,
  fetchLeadSummary,
  sendLeadEmail,
  bulkSendLeadEmails,
} from "@/lib/api";

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
  subscriber_count_previous?: number | null;
  subscriber_count_current?: number | null;
  subscriber_delta?: number | null;
  subscriber_refreshed_at?: string | null;
  email: string | null;
  email_status: string;
  review_status: "pending" | "promoted" | "blocked";
  block_reason: string | null;
  reviewed_at: string | null;
  discovered_at: string;
}

type ReviewStatus = "pending" | "promoted" | "blocked" | "all";
type LeadTabKey = "pending" | "promoted" | "grade-a" | "grade-b" | "grade-bp" | "blocked" | "all";

// ── 등급 라벨 / 색상 ──────────────────────────────────────────────────────────
const GRADE_LABEL: Record<string, string> = {
  A:   "유력리드",
  B:   "유망리드",
  "B?": "잠재리드",
  C:   "잠재리드",
};

const GRADE_COLOR: Record<string, string> = {
  A:   "bg-yellow-100 text-yellow-800",
  B:   "bg-blue-100 text-blue-800",
  "B?": "bg-purple-100 text-purple-700",
  C:   "bg-gray-100 text-gray-600",
};

// ── 이메일 상태 라벨 / 색상 ───────────────────────────────────────────────────
const EMAIL_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  "":           { label: "검토 대기",       color: "bg-amber-100 text-amber-700" },
  not_sent:     { label: "검토 대기",       color: "bg-amber-100 text-amber-700" },
  sent:         { label: "메일 전송 완료",  color: "bg-gray-100 text-gray-500" },
  replied:      { label: "메일 회신",       color: "bg-blue-100 text-blue-700" },
  meeting:      { label: "대면 미팅 진행중", color: "bg-purple-100 text-purple-700" },
  onboarding:   { label: "온보딩 진행중",   color: "bg-teal-100 text-teal-700" },
  completed:    { label: "온보딩 완료",     color: "bg-green-100 text-green-700" },
};

function getEmailStatusConfig(emailStatus: string) {
  return EMAIL_STATUS_CONFIG[emailStatus] ?? { label: "검토 대기", color: "bg-amber-100 text-amber-700" };
}

// ── API 훅 ────────────────────────────────────────────────────────────────────
function useLeads(reviewStatus: ReviewStatus, grade: string) {
  return useQuery<Lead[]>({
    queryKey: ["leads", reviewStatus, grade],
    queryFn: () => fetchLeads(reviewStatus, grade).then((d) => (d.items ?? []) as Lead[]),
    staleTime: 30_000,
  });
}

function usePromote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string }) => promoteLead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}

function useBlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => blockLead(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}

function useUnblock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unblockLead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}

function useRunC1() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerC1,
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["lead-summary"] }),
        qc.invalidateQueries({ queryKey: ["leads"] }),
      ]);
      await Promise.all([
        qc.refetchQueries({ queryKey: ["lead-summary"] }),
        qc.refetchQueries({ queryKey: ["leads"] }),
      ]);
    },
  });
}

function useRefreshSubscribers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: refreshLeadSubscribers,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["leads"] });
      void qc.invalidateQueries({ queryKey: ["lead-summary"] });
    },
  });
}

// ── 유틸 ──────────────────────────────────────────────────────────────────────
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

function fmtDelta(n: number | null | undefined) {
  if (n === null || n === undefined) return "-";
  if (n > 0) return `+${fmtSubs(n)}`;
  return fmtSubs(n);
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

// ── 메일 보내기 버튼 ──────────────────────────────────────────────────────────
function SendMailButton({
  lead,
  isSent,
  onSend,
  loading,
}: {
  lead: Lead;
  isSent: boolean;
  onSend: (lead: Lead) => void;
  loading: boolean;
}) {
  const alreadySent = isSent || lead.email_status === "sent";

  if (!lead.email) {
    return <span className="text-xs text-gray-300">이메일 없음</span>;
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 truncate max-w-[160px]" title={lead.email}>
        {lead.email}
      </span>
      {alreadySent ? (
        <button
          disabled
          className="px-2.5 py-1 text-xs font-medium rounded-lg bg-gray-100 text-gray-400 cursor-not-allowed whitespace-nowrap"
        >
          메일 전송 완료
        </button>
      ) : (
        <button
          onClick={() => onSend(lead)}
          disabled={loading}
          className="px-2.5 py-1 text-xs font-medium rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-50 whitespace-nowrap"
        >
          {loading ? "발송 중…" : "메일 보내기"}
        </button>
      )}
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────
export default function LeadDiscoveryPage() {
  const [tab, setTab] = useState<LeadTabKey>("pending");
  const [blockTarget, setBlockTarget] = useState<Lead | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  // 낙관적 UI: 현재 세션에서 메일 발송한 channel_id Set
  const [sentSet, setSentSet] = useState<Set<string>>(new Set());
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [bulkSending, setBulkSending] = useState(false);

  const TABS: {
    key: LeadTabKey;
    label: string;
    reviewStatus: ReviewStatus;
    grade: string;
    description: string;
  }[] = [
    {
      key: "pending",
      label: "검토대기",
      reviewStatus: "pending",
      grade: "",
      description: "발굴 후 아직 시드 승격 또는 차단 여부가 결정되지 않은 채널입니다.",
    },
    {
      key: "promoted",
      label: "시드 승격",
      reviewStatus: "promoted",
      grade: "",
      description: "검토 후 seed_channel로 승격되어 운영 대상에 포함된 채널입니다.",
    },
    {
      key: "grade-a",
      label: "유력리드(A)",
      reviewStatus: "all",
      grade: "A",
      description: "등급 분류 (A) 월간 숏츠 조회수 >= 2,000만",
    },
    {
      key: "grade-b",
      label: "유망리드(B)",
      reviewStatus: "all",
      grade: "B",
      description: "등급 분류 (B) 월간 숏츠 조회수 2,000만 미만 + 전월 대비 성장률 >= 10%",
    },
    {
      key: "grade-bp",
      label: "잠재리드(B?)",
      reviewStatus: "all",
      grade: "B?",
      description: "등급 분류 (B?) 월 500만 이상이면 잠재 후보",
    },
    {
      key: "blocked",
      label: "차단리스트",
      reviewStatus: "blocked",
      grade: "",
      description: "블록리스트 검토 후 제외 채널 영구 등록 (scripts/yt_shorts_blocklist.json) — 이후 재발견 방지",
    },
    {
      key: "all",
      label: "전체",
      reviewStatus: "all",
      grade: "",
      description: "전체 리드 채널을 월간 숏츠 조회수 기준으로 확인합니다.",
    },
  ];
  const activeTab = TABS.find((item) => item.key === tab) ?? TABS[0];
  const { data: leads = [], isLoading, error } = useLeads(activeTab.reviewStatus, activeTab.grade);
  const summary = useQuery({
    queryKey: ["lead-summary"],
    queryFn: fetchLeadSummary,
    staleTime: 30_000,
  });
  const promote = usePromote();
  const block = useBlock();
  const unblock = useUnblock();
  const runC1 = useRunC1();
  const refreshSubscribers = useRefreshSubscribers();
  const queryClient = useQueryClient();

  const showToast = (msg: string, type: "ok" | "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handlePromote = async (lead: Lead) => {
    try {
      await promote.mutateAsync({ id: lead.channel_id });
      showToast(`${lead.channel_name} → 시드 채널 승격 완료`, "ok");
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    }
  };

  const handleBlock = async (reason: string) => {
    if (!blockTarget) return;
    try {
      await block.mutateAsync({ id: blockTarget.channel_id, reason });
      showToast(`${blockTarget.channel_name} 차단 완료`, "ok");
      setBlockTarget(null);
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    }
  };

  const handleUnblock = async (lead: Lead) => {
    try {
      await unblock.mutateAsync(lead.channel_id);
      showToast(`${lead.channel_name} 차단 해제`, "ok");
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    }
  };

  const handleRunC1 = async () => {
    try {
      showToast("C-1 리드 발굴 실행 중…", "ok");
      await runC1.mutateAsync();
      setTab("pending");
      await Promise.all([
        queryClient.fetchQuery({
          queryKey: ["lead-summary"],
          queryFn: fetchLeadSummary,
          staleTime: 0,
        }),
        queryClient.fetchQuery({
          queryKey: ["leads", "pending", ""],
          queryFn: () => fetchLeads("pending", "").then((d) => (d.items ?? []) as Lead[]),
          staleTime: 0,
        }),
      ]);
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
      await queryClient.invalidateQueries({ queryKey: ["lead-summary"] });
      showToast("C-1 실행 완료. 검색 제목과 검토대기 목록을 반영했습니다.", "ok");
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    }
  };

  const handleRefreshSubscribers = async () => {
    try {
      const res = await refreshSubscribers.mutateAsync();
      await queryClient.fetchQuery({
        queryKey: ["leads", activeTab.reviewStatus, activeTab.grade],
        queryFn: () =>
          fetchLeads(activeTab.reviewStatus, activeTab.grade).then((d) => (d.items ?? []) as Lead[]),
        staleTime: 0,
      });
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
      showToast(`구독자 수 갱신 완료 — ${res.updated}/${res.total}개`, "ok");
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    }
  };

  const handleSendMail = async (lead: Lead) => {
    setSendingId(lead.channel_id);
    try {
      await sendLeadEmail(lead.channel_id);
      setSentSet((prev) => new Set([...prev, lead.channel_id]));
      showToast(`${lead.channel_name}에 콜드메일 발송 완료`, "ok");
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    } finally {
      setSendingId(null);
    }
  };

  const handleBulkSendMail = async () => {
    const targets = leads.filter(
      (l) => l.email && l.email_status !== "sent" && !sentSet.has(l.channel_id)
    );
    if (targets.length === 0) {
      showToast("발송 가능한 채널이 없습니다.", "err");
      return;
    }
    setBulkSending(true);
    try {
      const res = await bulkSendLeadEmails(false);
      // 낙관적 업데이트: 현재 목록의 대상 전체 sent 처리
      setSentSet((prev) => {
        const next = new Set(prev);
        targets.forEach((l) => next.add(l.channel_id));
        return next;
      });
      showToast(`일괄 발송 완료 — ${res.sent}건 성공${res.failed > 0 ? `, ${res.failed}건 실패` : ""}`, "ok");
    } catch (e: unknown) {
      showToast((e as Error).message, "err");
    } finally {
      setBulkSending(false);
    }
  };

  // 검토 대기 탭에서 미발송(이메일 있음) 채널 수
  const pendingEmailCount = tab === "pending"
    ? leads.filter((l) => l.email && l.email_status !== "sent" && !sentSet.has(l.channel_id)).length
    : 0;

  return (
    <div className="p-8">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">리드 채널 관리</h1>
          <p className="text-sm text-gray-400 mt-1">
            발굴된 채널을 검토하고 콜드메일을 발송하거나 시드 채널로 승격합니다.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex gap-2">
            <button
              onClick={handleRefreshSubscribers}
              disabled={refreshSubscribers.isPending}
              className="flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {refreshSubscribers.isPending ? "갱신 중…" : "구독자 새로고침"}
            </button>
            <button
              onClick={handleRunC1}
              disabled={runC1.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {runC1.isPending ? "실행 중…" : "리드 발굴 실행"}
            </button>
          </div>
          <p className="text-xs text-gray-400">
            진행률 {summary.data?.progress_percent ?? 0}% · 최근 실행{" "}
            {summary.data?.last_run_at ? new Date(summary.data.last_run_at).toLocaleString("ko-KR") : "-"}
            {" "}· 이번 실행 제외 {summary.data?.excluded_count ?? 0}건
          </p>
          {summary.data?.discovery_message && (
            <p className="max-w-xl text-right text-sm font-semibold text-red-600">
              {summary.data.discovery_message}
            </p>
          )}
        </div>
      </div>

      {/* 탭 영역 */}
      <div className="mb-4">
        <div className="flex flex-wrap gap-1 bg-gray-100 rounded-lg p-1">
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
        <p className="mt-2 text-sm text-gray-500">{activeTab.description}</p>
      </div>

      <section className="mb-4 rounded-xl border border-gray-200 bg-white p-4">
        <div className="mb-4 rounded-lg bg-gray-50 p-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span className="font-semibold text-gray-900">
              신규 발굴 채널 수: {summary.data?.new_lead_count ?? 0}
            </span>
            <span className="text-gray-500">
              후보 {summary.data?.discovered_count ?? 0}개 · 제외 {summary.data?.excluded_count ?? 0}개
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">최근 발굴 검색 제목</h2>
            <p className="mt-1 text-xs text-gray-400">
              TMDB/KOBIS 기준 최근 인기·방영/개봉 작품에서 선정한 Layer B 검색 제목입니다.
            </p>
          </div>
          <span className="text-xs text-gray-400">
            {summary.data?.drama_titles?.length ?? 0}개
          </span>
        </div>
        {summary.data?.drama_titles?.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {summary.data.drama_titles.map((title) => (
              <span
                key={title}
                className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700"
              >
                {title}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-gray-400">
            아직 최근 실행 로그에 검색 제목이 없습니다. 다음 리드 발굴 실행 후 표시됩니다.
          </p>
        )}
        {Array.isArray(summary.data?.detail_log) && summary.data.detail_log.length > 0 && (
          <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">최근 발굴 상세</p>
            <ul className="mt-2 space-y-1">
              {summary.data.detail_log.slice(0, 8).map((item: { message?: string }, index: number) => (
                <li key={`${item.message ?? "log"}-${index}`} className="text-xs text-gray-600">
                  {item.message ?? JSON.stringify(item)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">채널</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">등급</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">월간 숏츠 조회</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">이전 구독자</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">현재 구독자</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">증감 추이</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">발굴일</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">상태</th>
              {tab === "pending" && (
                <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase tracking-wide">콜드메일</th>
              )}
              <th className="px-5 py-3.5 text-right text-xs text-gray-500 font-semibold uppercase tracking-wide">액션</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={tab === "pending" ? 10 : 9} className="px-5 py-12 text-center text-sm text-gray-400">
                  불러오는 중…
                </td>
              </tr>
            )}
            {!isLoading && error && (
              <tr>
                <td colSpan={tab === "pending" ? 10 : 9} className="px-5 py-12 text-center text-sm text-red-400">
                  오류: {(error as Error).message}
                </td>
              </tr>
            )}
            {!isLoading && !error && leads.length === 0 && (
              <tr>
                <td colSpan={tab === "pending" ? 10 : 9} className="px-5 py-12 text-center text-sm text-gray-400">
                  해당하는 채널이 없습니다.
                </td>
              </tr>
            )}
            {leads.map((lead) => {
              const emailStatusCfg = getEmailStatusConfig(
                sentSet.has(lead.channel_id) ? "sent" : lead.email_status
              );
              return (
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
                      {GRADE_LABEL[lead.grade ?? "C"] ?? lead.grade ?? "-"}
                    </span>
                  </td>

                  {/* 월간 조회 */}
                  <td className="px-5 py-4 text-sm text-gray-700 tabular-nums">
                    {fmtViews(lead.monthly_views)}
                  </td>

                  {/* 이전 구독자 */}
                  <td className="px-5 py-4 text-sm text-gray-700 tabular-nums">
                    {fmtSubs(lead.subscriber_count_previous ?? null)}
                  </td>

                  {/* 현재 구독자 */}
                  <td className="px-5 py-4 text-sm text-gray-700 tabular-nums">
                    {fmtSubs(lead.subscriber_count_current ?? lead.subscriber_count)}
                  </td>

                  {/* 증감 */}
                  <td className={`px-5 py-4 text-sm font-medium tabular-nums ${
                    (lead.subscriber_delta ?? 0) > 0 ? "text-emerald-600" : (lead.subscriber_delta ?? 0) < 0 ? "text-red-500" : "text-gray-500"
                  }`}>
                    {fmtDelta(lead.subscriber_delta)}
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
                      <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full ${emailStatusCfg.color}`}>
                        {emailStatusCfg.label}
                      </span>
                    )}
                  </td>

                  {/* 콜드메일 (검토 대기 탭만) */}
                  {tab === "pending" && (
                    <td className="px-5 py-4">
                      <SendMailButton
                        lead={lead}
                        isSent={sentSet.has(lead.channel_id)}
                        onSend={handleSendMail}
                        loading={sendingId === lead.channel_id}
                      />
                    </td>
                  )}

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
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 일괄 메일 보내기 (검토 대기 탭만) */}
      {tab === "pending" && !isLoading && leads.length > 0 && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-gray-400">
            발송 가능 채널:{" "}
            <span className="font-semibold text-gray-600">{pendingEmailCount}개</span>
          </p>
          <button
            onClick={handleBulkSendMail}
            disabled={bulkSending || pendingEmailCount === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            {bulkSending ? "발송 중…" : `일괄 메일 보내기 (${pendingEmailCount}건)`}
          </button>
        </div>
      )}

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
            toast.type === "ok" ? "bg-gray-900 text-white" : "bg-red-500 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
