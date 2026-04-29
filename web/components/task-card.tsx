"use client";

import { useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { startRun } from "@/lib/api";
import { cn, categoryColor, categoryBadge, getCategoryFromId } from "@/lib/utils";
import { Button } from "./ui/button";
import { RunStatusBadge } from "./run-status-badge";
import type { IntegrationTaskSpec, IntegrationRun, ExecutionMode } from "@/lib/types";

interface TaskCardProps {
  task: IntegrationTaskSpec;
  latestRun?: IntegrationRun | null;
  onRunStarted?: (run: IntegrationRun) => void;
}

export function TaskCard({ task, latestRun, onRunStarted }: TaskCardProps) {
  const cat = getCategoryFromId(task.task_id);
  const [payload, setPayload] = useState(
    JSON.stringify(task.default_payload, null, 2)
  );
  const [approved, setApproved] = useState(false);
  const [payloadError, setPayloadError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: ({
      mode,
      approvedFlag,
    }: {
      mode: ExecutionMode;
      approvedFlag: boolean;
    }) => {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(payload);
      } catch {
        throw new Error("payload JSON 파싱 실패");
      }
      return startRun(task.task_id, parsed, mode, approvedFlag);
    },
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      onRunStarted?.(run);
    },
    onError: (e: Error) => setPayloadError(e.message),
  });

  const handleRun = useCallback(
    (mode: ExecutionMode) => {
      setPayloadError("");
      try {
        JSON.parse(payload);
      } catch {
        setPayloadError("유효하지 않은 JSON입니다.");
        return;
      }
      mutate({ mode, approvedFlag: approved });
    },
    [mutate, payload, approved]
  );

  const relatedLinks = Object.entries(task.sheet_links ?? {}).filter(
    ([k, v]) => k !== "로그시트" && v
  );
  const logLink = task.sheet_links?.["로그시트"] ?? "";

  return (
    <article
      className={cn(
        "rounded-xl border bg-gradient-to-br shadow-sm overflow-hidden",
        categoryColor[cat] ?? "from-gray-50 to-gray-100 border-gray-200"
      )}
    >
      {/* 헤더 */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/60">
        <span
          className={cn(
            "rounded-md px-2 py-0.5 text-xs font-bold tracking-wide",
            categoryBadge[cat] ?? "bg-gray-600 text-white"
          )}
        >
          {task.task_id}
        </span>
        <h3 className="flex-1 font-semibold text-sm text-gray-800 leading-tight">
          {task.title.replace(/^[A-Z]-\d+\s+/, "")}
        </h3>
        {latestRun && <RunStatusBadge status={latestRun.status} />}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="상세 펼치기"
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* 바디 */}
      <div className="p-4 space-y-3 bg-white/70">
        {/* 설명 */}
        <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-wrap line-clamp-3">
          {task.description}
        </p>

        {/* 태그 */}
        <div className="flex flex-wrap gap-1.5">
          {task.targets.map((t) => (
            <span
              key={t}
              className="text-[11px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5"
            >
              {t}
            </span>
          ))}
          {task.requires_approval && (
            <span className="text-[11px] bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 font-medium">
              승인 필요
            </span>
          )}
        </div>

        {/* 관련 링크 */}
        {relatedLinks.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {relatedLinks.map(([name, url]) => (
              <a
                key={name}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-full px-2.5 py-0.5 transition-colors"
              >
                {name}
                <ExternalLink size={10} />
              </a>
            ))}
            {logLink && (
              <a
                href={logLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] bg-gray-100 hover:bg-gray-200 text-gray-500 rounded-full px-2.5 py-0.5 transition-colors"
              >
                로그
                <ExternalLink size={10} />
              </a>
            )}
          </div>
        )}

        {/* 펼치기 영역 */}
        {expanded && (
          <div className="space-y-3 pt-1 border-t border-gray-100">
            {/* 경고 */}
            {task.real_run_warning && (
              <div className="flex gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3">
                <AlertTriangle size={14} className="text-amber-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800 whitespace-pre-wrap">
                  {task.real_run_warning}
                </p>
              </div>
            )}

            {/* Payload 에디터 */}
            <div>
              <label className="block text-[11px] text-gray-500 mb-1 font-medium uppercase tracking-wide">
                Payload
              </label>
              <textarea
                value={payload}
                onChange={(e) => {
                  setPayload(e.target.value);
                  setPayloadError("");
                }}
                rows={Math.min(12, payload.split("\n").length + 1)}
                className="w-full rounded-lg border border-gray-200 bg-gray-900 text-green-300 font-mono text-[11px] px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
                spellCheck={false}
              />
              {payloadError && (
                <p className="text-xs text-red-600 mt-1">{payloadError}</p>
              )}
            </div>

            {/* 승인 체크 */}
            {task.requires_approval && (
              <label className="flex items-center gap-2 text-xs text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={approved}
                  onChange={(e) => setApproved(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                실제 실행 승인
              </label>
            )}

            {/* 실행 버튼 */}
            <div className="flex gap-2 justify-end">
              {task.supports_dry_run && (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={isPending}
                  onClick={() => handleRun("dry_run")}
                >
                  🧪 Dry Run
                </Button>
              )}
              <Button
                variant="primary"
                size="sm"
                loading={isPending}
                onClick={() => handleRun("real_run")}
              >
                🚀 Real Run
              </Button>
            </div>
          </div>
        )}

        {/* 접힌 상태의 빠른 실행 버튼 */}
        {!expanded && (
          <div className="flex gap-2 justify-end">
            {task.supports_dry_run && (
              <Button
                variant="ghost"
                size="sm"
                loading={isPending}
                onClick={() => handleRun("dry_run")}
              >
                🧪 Dry Run
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              loading={isPending}
              onClick={() => {
                setExpanded(true);
              }}
            >
              🚀 실행
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}
