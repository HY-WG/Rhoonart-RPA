"use client";

import { useState } from "react";
import { ToolsPanel } from "@/components/tools-panel";
import { RunLogViewer } from "@/components/run-log-viewer";
import { useQuery } from "@tanstack/react-query";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function HomepageAutoPage() {
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
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 max-w-7xl">
      <div className="xl:col-span-2">
        <ToolsPanel
          tabGroup="homepage_auto"
          subtitle="홈페이지(laeebly.io)를 통해 인입되는 크리에이터 요청을 자동 처리합니다."
          onRunStarted={setSelectedRun}
        />
      </div>
      <div className="space-y-4">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 className="font-semibold text-sm text-gray-900 mb-4">
            실행 결과
          </h3>
          <RunLogViewer run={displayRun ?? null} />
        </div>
      </div>
    </div>
  );
}
