"use client";

import { useEffect, useRef } from "react";
import { RunStatusBadge } from "./run-status-badge";
import type { IntegrationRun } from "@/lib/types";

export function RunLogViewer({ run }: { run: IntegrationRun | null }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [run?.logs]);

  if (!run) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        좌측에서 작업을 실행하면 결과가 여기 표시됩니다.
      </div>
    );
  }

  const resultBody =
    (run.result as Record<string, unknown> | null)?.body ??
    run.result ??
    {};

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-medium text-sm text-gray-800">{run.title}</span>
        <RunStatusBadge status={run.status} />
        <span className="text-xs text-gray-400 bg-gray-50 rounded px-1.5 py-0.5 font-mono">
          {run.execution_mode}
        </span>
        {typeof (resultBody as Record<string,unknown>)?.crawl_seconds === "number" && (
          <span className="text-xs bg-green-50 text-green-700 rounded px-1.5 py-0.5">
            crawl: {String((resultBody as Record<string,unknown>).crawl_seconds)}s
          </span>
        )}
        {typeof (resultBody as Record<string,unknown>)?.elapsed_seconds === "number" && (
          <span className="text-xs bg-green-50 text-green-700 rounded px-1.5 py-0.5">
            elapsed: {String((resultBody as Record<string,unknown>).elapsed_seconds)}s
          </span>
        )}
      </div>

      {/* 로그 */}
      <div className="bg-gray-900 rounded-lg p-4 font-mono text-xs text-green-400 max-h-56 overflow-y-auto">
        {run.logs.length === 0 ? (
          <span className="text-gray-500">로그 없음</span>
        ) : (
          run.logs.map((line, i) => (
            <div key={i} className="leading-5">
              {line}
            </div>
          ))
        )}
        {run.status === "running" && (
          <span className="inline-block w-2 h-3.5 bg-green-400 animate-pulse ml-0.5" />
        )}
        <div ref={bottomRef} />
      </div>

      {/* 에러 */}
      {run.error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700">
          {run.error}
        </div>
      )}

      {/* 결과 JSON */}
      {run.result && (
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
            결과 JSON 보기
          </summary>
          <pre className="mt-2 bg-gray-50 rounded p-3 overflow-x-auto text-gray-700 text-[11px]">
            {JSON.stringify(run.result, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
