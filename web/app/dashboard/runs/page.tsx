"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RunHistory } from "@/components/run-history";
import { RunLogViewer } from "@/components/run-log-viewer";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function RunsPage() {
  const [selectedRun, setSelectedRun] = useState<IntegrationRun | null>(null);
  const { data: polledRun } = useQuery({ queryKey: ["run", selectedRun?.run_id], queryFn: () => fetchRun(selectedRun!.run_id), enabled: !!selectedRun && (selectedRun.status === "queued" || selectedRun.status === "running"), refetchInterval: 1500 });
  return <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-6xl"><div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"><div className="flex items-center justify-between mb-4"><h3 className="font-semibold text-sm text-gray-900">{"\uc2e4\ud589 \uae30\ub85d"}</h3><span className="text-xs text-gray-400">{"\ucd5c\uadfc 30\uac1c, 4\ucd08\ub9c8\ub2e4 \uac31\uc2e0"}</span></div><RunHistory selectedRunId={selectedRun?.run_id} onSelect={setSelectedRun} limit={30} /></div><div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"><h3 className="font-semibold text-sm text-gray-900 mb-4">{"\uc2e4\ud589 \uc0c1\uc138"}</h3><RunLogViewer run={polledRun ?? selectedRun ?? null} /></div></div>;
}
