"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPendingApprovals,
  approveRun,
  rejectRun,
} from "@/lib/api";
import type { ApprovalRecord } from "@/lib/types";

const RISK_COLOR: Record<string, string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

function ApprovalCard({
  record,
  onApprove,
  onReject,
  loading,
}: {
  record: ApprovalRecord;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  loading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
              {record.task_id}
            </span>
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded ${
                RISK_COLOR[record.risk_level] ?? RISK_COLOR.medium
              }`}
            >
              위험도 {record.risk_level}
            </span>
          </div>
          <p className="text-sm font-medium text-gray-900 mt-1">{record.summary}</p>
          <p className="text-xs text-gray-400">
            요청 시각: {new Date(record.requested_at).toLocaleString("ko-KR")}
          </p>
        </div>

        {/* 버튼 */}
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => onApprove(record.approval_id)}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 text-white
                       hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            승인
          </button>
          <button
            onClick={() => onReject(record.approval_id)}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-100 text-red-700
                       hover:bg-red-200 disabled:opacity-50 transition-colors"
          >
            거절
          </button>
        </div>
      </div>

      {/* 미리보기 토글 */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="text-xs text-blue-500 hover:underline"
      >
        {expanded ? "▲ 미리보기 닫기" : "▼ 실행 미리보기 보기"}
      </button>

      {expanded && (
        <pre className="text-xs bg-gray-50 border border-gray-100 rounded-lg p-3 overflow-auto max-h-48 text-gray-700">
          {JSON.stringify(record.preview, null, 2)}
        </pre>
      )}

      <p className="text-[10px] text-gray-400 font-mono">
        approval_id: {record.approval_id} · trace_id: {record.trace_id}
      </p>
    </div>
  );
}

export default function ApprovalsPage() {
  const queryClient = useQueryClient();

  const {
    data: records = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: fetchPendingApprovals,
    refetchInterval: 5000,
  });

  const [actionId, setActionId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const approveMut = useMutation({
    mutationFn: (id: string) => approveRun(id),
    onMutate: (id) => setActionId(id),
    onSuccess: (_, id) => {
      showToast(`승인 완료 (${id})`, true);
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (err) => showToast(`승인 실패: ${(err as Error).message}`, false),
    onSettled: () => setActionId(null),
  });

  const rejectMut = useMutation({
    mutationFn: (id: string) => rejectRun(id),
    onMutate: (id) => setActionId(id),
    onSuccess: (_, id) => {
      showToast(`거절 완료 (${id})`, true);
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
    onError: (err) => showToast(`거절 실패: ${(err as Error).message}`, false),
    onSettled: () => setActionId(null),
  });

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 토스트 */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl text-sm font-semibold shadow-lg transition-all
            ${toast.ok ? "bg-emerald-600 text-white" : "bg-red-600 text-white"}`}
        >
          {toast.msg}
        </div>
      )}

      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">승인 대기</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            고위험 작업 실행 전 HITL 체크포인트 — 검토 후 승인 또는 거절하세요.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-3 py-1.5 rounded-lg transition-colors"
        >
          새로고침
        </button>
      </div>

      {/* 배지 */}
      <div className="flex items-center gap-2">
        <span
          className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
            records.length > 0
              ? "bg-amber-100 text-amber-700"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          {records.length}건 대기 중
        </span>
        <span className="text-xs text-gray-400">5초마다 자동 갱신</span>
      </div>

      {/* 목록 */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="py-12 text-center text-sm text-red-500 bg-red-50 rounded-xl border border-red-100">
          백엔드 연결 실패 — Python API(localhost:8001)가 실행 중인지 확인하세요.
        </div>
      ) : records.length === 0 ? (
        <div className="py-16 text-center text-sm text-gray-400 bg-gray-50 rounded-xl border border-gray-100">
          대기 중인 승인 요청이 없습니다.
        </div>
      ) : (
        <div className="space-y-4">
          {records.map((rec) => (
            <ApprovalCard
              key={rec.approval_id}
              record={rec}
              loading={actionId === rec.approval_id}
              onApprove={(id) => approveMut.mutate(id)}
              onReject={(id) => rejectMut.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
