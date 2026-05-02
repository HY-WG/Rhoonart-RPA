"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ToolsPanel } from "@/components/tools-panel";
import { RunLogViewer } from "@/components/run-log-viewer";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function HomepageAutoPage() {
  const [selectedRun, setSelectedRun] = useState<IntegrationRun | null>(null);
  const { data: polledRun } = useQuery({ queryKey: ["run", selectedRun?.run_id], queryFn: () => fetchRun(selectedRun!.run_id), enabled: !!selectedRun && (selectedRun.status === "queued" || selectedRun.status === "running"), refetchInterval: 1500 });
  return <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 max-w-7xl"><div className="xl:col-span-2"><ToolsPanel tabGroup="homepage_auto" subtitle={"\ud648\ud398\uc774\uc9c0\ub97c \ud1b5\ud574 \ub4e4\uc5b4\uc624\ub294 \ud06c\ub9ac\uc5d0\uc774\ud130 \uc694\uccad\uc744 \uc790\ub3d9\uc73c\ub85c \ucc98\ub9ac\ud569\ub2c8\ub2e4."} onRunStarted={setSelectedRun} /></div><div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"><h3 className="font-semibold text-sm text-gray-900 mb-4">{"\uc2e4\ud589 \uacb0\uacfc"}</h3><RunLogViewer run={polledRun ?? selectedRun ?? null} /></div></div>;
}
