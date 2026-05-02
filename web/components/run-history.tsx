"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchRuns } from "@/lib/api";
import { RunStatusBadge } from "./run-status-badge";
import { categoryBadge, cn, getCategoryFromId, relativeTime } from "@/lib/utils";
import type { IntegrationRun } from "@/lib/types";

export function RunHistory({ selectedRunId, onSelect, limit = 20, compact = false }: { selectedRunId?: string | null; onSelect?: (run: IntegrationRun) => void; limit?: number; compact?: boolean }) {
  const { data: runs = [], isLoading } = useQuery({ queryKey: ["runs"], queryFn: () => fetchRuns(limit), refetchInterval: 4000 });
  if (isLoading) return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />)}</div>;
  if (runs.length === 0) return <div className="text-center py-10 text-gray-400 text-sm">{"\uc544\uc9c1 \uc2e4\ud589 \uae30\ub85d\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."}</div>;
  return <div className="space-y-2">{runs.map((run) => { const cat = getCategoryFromId(run.task_id); const isSelected = run.run_id === selectedRunId; return <button key={run.run_id} type="button" onClick={() => onSelect?.(run)} className={cn("w-full text-left rounded-lg border px-3 py-2.5 transition-colors", isSelected ? "bg-blue-50 border-blue-200" : "bg-white border-gray-100 hover:bg-gray-50")}><div className="flex items-center gap-2"><span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold", categoryBadge[cat] ?? "bg-gray-600 text-white")}>{run.task_id}</span><span className="flex-1 text-xs font-medium text-gray-700 truncate">{compact ? run.title.replace(/^[A-Z]-\d+\s+/, "") : run.title}</span><RunStatusBadge status={run.status} /></div>{!compact && <div className="flex items-center gap-2 mt-1"><span className="text-[10px] text-gray-400 font-mono">{run.run_id}</span><span className="text-[10px] text-gray-400">{relativeTime(run.started_at)}</span><span className={cn("text-[10px] rounded px-1 py-0.5", run.execution_mode === "real_run" ? "bg-red-50 text-red-600" : "bg-gray-100 text-gray-500")}>{run.execution_mode}</span></div>}</button>; })}</div>;
}
