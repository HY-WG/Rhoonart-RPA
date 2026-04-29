"use client";

import { useState } from "react";
import { ToolsPanel } from "@/components/tools-panel";
import { RunLogViewer } from "@/components/run-log-viewer";
import { useQuery } from "@tanstack/react-query";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function OpsAdminPage() {
  const [selectedRun, setSelectedRun] = useState<IntegrationRun | null>(null);

  // 실행 중인 경우 폴링
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
      {/* 좌측: 작업 목록 */}
      <div className="xl:col-span-2">
        <ToolsPanel
          tabGroup="ops_admin"
          subtitle="운영 팀이 직접 실행·모니터링하는 자동화 도구입니다."
          onRunStarted={setSelectedRun}
        />
      </div>

      {/* 우측: 실행 결과 */}
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
