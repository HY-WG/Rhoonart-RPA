"use client";

import { useState } from "react";
import { RunHistory } from "@/components/run-history";
import { RunLogViewer } from "@/components/run-log-viewer";
import { useQuery } from "@tanstack/react-query";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function RunsPage() {
  const [selectedRun, setSelectedRun] = useState<IntegrationRun | null>(null);

  const { data: polledRun } = useQuery({
    queryKey: ["run", selectedRun?.run_id],
    queryFn: () => fetchRun(selectedRun!.run_id),
    enabled:
      !!selectedRun &&
      (selectedRun.status === "queued" || selectedRun.status === "running"),
    refetchInterval: 1500,
  });

  const displayRun = polledRun ?? selectedRun;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-6xl">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-sm text-gray-900">실행 기록</h3>
          <span className="text-xs text-gray-400">최근 30개 · 4초 갱신</span>
        </div>
        <RunHistory
          selectedRunId={selectedRun?.run_id}
          onSelect={setSelectedRun}
          limit={30}
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
        <h3 className="font-semibold text-sm text-gray-900 mb-4">실행 상세</h3>
        <RunLogViewer run={displayRun ?? null} />
      </div>
    </div>
  );
}
