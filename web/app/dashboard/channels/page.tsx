"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChannelPanel } from "@/components/channel-panel";
import { RunLogViewer } from "@/components/run-log-viewer";
import { fetchRun } from "@/lib/api";
import type { IntegrationRun } from "@/lib/types";

export default function ChannelsPage() {
  const [selectedRun, setSelectedRun] = useState<IntegrationRun | null>(null);
  const { data: polledRun } = useQuery({ queryKey: ["run", selectedRun?.run_id], queryFn: () => fetchRun(selectedRun!.run_id), enabled: !!selectedRun && (selectedRun.status === "queued" || selectedRun.status === "running"), refetchInterval: 1500 });
  return <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 max-w-7xl"><div className="xl:col-span-2"><ChannelPanel onRunStarted={setSelectedRun} /></div><div><div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"><h3 className="font-semibold text-sm text-gray-900 mb-4">{"\uc561\uc158 \uacb0\uacfc"}</h3><RunLogViewer run={polledRun ?? selectedRun ?? null} /></div></div></div>;
}
