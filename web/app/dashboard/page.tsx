"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchRuns, fetchPendingApprovals } from "@/lib/api";
import { RunStatusBadge } from "@/components/run-status-badge";
import { relativeTime, categoryBadge, getCategoryFromId, cn } from "@/lib/utils";
import type { RunStatus } from "@/lib/types";

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={cn("text-3xl font-bold mt-1", color)}>{value}</p>
    </div>
  );
}

export default function DashboardHome() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: () => fetchRuns(50),
    refetchInterval: 5000,
  });

  const { data: pendingApprovals = [] } = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: fetchPendingApprovals,
    refetchInterval: 5000,
  });

  const counts: Record<RunStatus, number> = {
    queued: 0,
    running: 0,
    succeeded: 0,
    failed: 0,
  };
  for (const r of runs) {
    counts[r.status] = (counts[r.status] ?? 0) + 1;
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-xl font-bold text-gray-900">전체 현황</h2>
        <p className="text-sm text-gray-400 mt-0.5">
          {new Date().toLocaleDateString("ko-KR", {
            year: "numeric",
            month: "long",
            day: "numeric",
            weekday: "long",
          })}
        </p>
      </div>

      {/* 승인 대기 배너 */}
      {pendingApprovals.length > 0 && (
        <Link
          href="/dashboard/approvals"
          className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 hover:bg-amber-100 transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="text-amber-500 text-lg">⚠️</span>
            <span className="text-sm font-semibold text-amber-800">
              승인 대기 {pendingApprovals.length}건 — 고위험 작업 실행 전 검토가 필요합니다.
            </span>
          </div>
          <span className="text-xs text-amber-600 font-medium">검토하기 →</span>
        </Link>
      )}

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="전체 실행" value={runs.length} color="text-gray-800" />
        <StatCard label="성공" value={counts.succeeded} color="text-green-600" />
        <StatCard label="실패" value={counts.failed} color="text-red-600" />
        <StatCard
          label="실행 중"
          value={counts.running + counts.queued}
          color="text-amber-600"
        />
      </div>

      {/* 최근 실행 */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-sm text-gray-900">최근 실행 기록</h3>
        </div>
        {isLoading ? (
          <div className="p-5 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {runs.slice(0, 10).map((run) => {
              const cat = getCategoryFromId(run.task_id);
              return (
                <div
                  key={run.run_id}
                  className="flex items-center gap-3 px-5 py-3 hover:bg-gray-50 transition-colors"
                >
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-bold",
                      categoryBadge[cat] ?? "bg-gray-600 text-white"
                    )}
                  >
                    {run.task_id}
                  </span>
                  <span className="flex-1 text-sm text-gray-700 truncate">
                    {run.title.replace(/^[A-Z]-\d+\s+/, "")}
                  </span>
                  <RunStatusBadge status={run.status} />
                  <span className="text-xs text-gray-400 w-20 text-right">
                    {relativeTime(run.started_at)}
                  </span>
                </div>
              );
            })}
            {runs.length === 0 && (
              <div className="py-12 text-center text-sm text-gray-400">
                실행 기록이 없습니다.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
