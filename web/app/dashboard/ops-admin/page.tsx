"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ToolsPanel } from "@/components/tools-panel";
import { RunLogViewer } from "@/components/run-log-viewer";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function OpsAdminPage() {
  const [selectedRun, setSelectedRun] = useState<IntegrationRun | null>(null);
  const { data: polledRun } = useQuery({ queryKey: ["run", selectedRun?.run_id], queryFn: () => fetchRun(selectedRun!.run_id), enabled: !!selectedRun && (selectedRun.status === "queued" || selectedRun.status === "running"), refetchInterval: 1500 });
  return <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 max-w-7xl"><div className="xl:col-span-2"><ToolsPanel tabGroup="ops_admin" subtitle={"\uc6b4\uc601\ud300\uc774 \uc9c1\uc811 \uc2e4\ud589\ud558\uace0 \ubaa8\ub2c8\ud130\ub9c1\ud558\ub294 \uad00\ub9ac \ub3c4\uad6c\uc785\ub2c8\ub2e4."} onRunStarted={setSelectedRun} /></div><div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"><h3 className="font-semibold text-sm text-gray-900 mb-4">{"\uc2e4\ud589 \uacb0\uacfc"}</h3><RunLogViewer run={polledRun ?? selectedRun ?? null} /></div></div>;
}
