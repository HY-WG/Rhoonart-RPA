"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchTasks, fetchRuns } from "@/lib/api";
import { TaskCard } from "./task-card";
import type { IntegrationRun } from "@/lib/types";

interface ToolsPanelProps {
  tabGroup: string;
  subtitle: string;
  onRunStarted?: (run: IntegrationRun) => void;
}

export function ToolsPanel({ tabGroup, subtitle, onRunStarted }: ToolsPanelProps) {
  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: fetchTasks,
    staleTime: 60_000,
  });

  const { data: runs = [] } = useQuery({
    queryKey: ["runs"],
    queryFn: () => fetchRuns(30),
    refetchInterval: 4000,
  });

  const filtered = tasks.filter(
    (t) => (t.tab_group ?? "ops_admin") === tabGroup
  );

  const latestRunByTask = Object.fromEntries(
    filtered.map((t) => [
      t.task_id,
      runs.find((r) => r.task_id === t.task_id) ?? null,
    ])
  );

  return (
    <section className="space-y-4">
      <p className="text-sm text-gray-500">{subtitle}</p>
      {tasksLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-48 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm rounded-xl bg-gray-50 border border-gray-100">
          {tasks.length === 0
            ? "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요."
            : "등록된 도구가 없습니다."}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((task) => (
            <TaskCard
              key={task.task_id}
              task={task}
              latestRun={latestRunByTask[task.task_id]}
              onRunStarted={onRunStarted}
            />
          ))}
        </div>
      )}
    </section>
  );
}
