"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchRuns, fetchTasks } from "@/lib/api";
import { TaskCard } from "./task-card";
import type { IntegrationRun } from "@/lib/types";

export function ToolsPanel({ tabGroup, subtitle, onRunStarted }: { tabGroup: string; subtitle: string; onRunStarted?: (run: IntegrationRun) => void }) {
  const { data: tasks = [], isLoading: tasksLoading } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks, staleTime: 60_000 });
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: () => fetchRuns(30), refetchInterval: 4000 });
  const filtered = tasks.filter((t) => (t.tab_group ?? "ops_admin") === tabGroup);
  const latestRunByTask = Object.fromEntries(filtered.map((t) => [t.task_id, runs.find((r) => r.task_id === t.task_id) ?? null]));
  return <section className="space-y-4"><p className="text-sm text-gray-500">{subtitle}</p>{tasksLoading ? <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-48 rounded-xl bg-gray-100 animate-pulse" />)}</div> : filtered.length === 0 ? <div className="text-center py-16 text-gray-400 text-sm rounded-xl bg-gray-50 border border-gray-100">{tasks.length === 0 ? "\uc11c\ubc84\uc5d0 \uc5f0\uacb0\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4. Python API\uac00 \uc2e4\ud589 \uc911\uc778\uc9c0 \ud655\uc778\ud574\uc8fc\uc138\uc694." : "\ub4f1\ub85d\ub41c \ub3c4\uad6c\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}</div> : <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{filtered.map((task) => <TaskCard key={task.task_id} task={task} latestRun={latestRunByTask[task.task_id]} onRunStarted={onRunStarted} />)}</div>}</section>;
}
