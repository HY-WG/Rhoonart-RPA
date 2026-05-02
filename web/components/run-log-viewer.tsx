"use client";

import { useEffect, useRef } from "react";
import { RunStatusBadge } from "./run-status-badge";
import type { IntegrationRun } from "@/lib/types";

export function RunLogViewer({ run }: { run: IntegrationRun | null }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [run?.logs]);
  if (!run) return <div className="flex items-center justify-center h-40 text-gray-400 text-sm">{"\uc791\uc5c5\uc744 \uc2e4\ud589\ud558\uba74 \uacb0\uacfc\uac00 \uc5ec\uae30\uc5d0 \ud45c\uc2dc\ub429\ub2c8\ub2e4."}</div>;
  const resultBody = (run.result as Record<string, unknown> | null)?.body ?? run.result ?? {};
  return <div className="space-y-3"><div className="flex items-center gap-2 flex-wrap"><span className="font-medium text-sm text-gray-800">{run.title}</span><RunStatusBadge status={run.status} /><span className="text-xs text-gray-400 bg-gray-50 rounded px-1.5 py-0.5 font-mono">{run.execution_mode}</span>{typeof (resultBody as Record<string, unknown>)?.crawl_seconds === "number" && <span className="text-xs bg-green-50 text-green-700 rounded px-1.5 py-0.5">crawl: {String((resultBody as Record<string, unknown>).crawl_seconds)}s</span>}</div><div className="bg-gray-900 rounded-lg p-4 font-mono text-xs text-green-400 max-h-56 overflow-y-auto">{run.logs.length === 0 ? <span className="text-gray-500">{"\ub85c\uadf8 \uc5c6\uc74c"}</span> : run.logs.map((line, i) => <div key={i} className="leading-5">{line}</div>)}{run.status === "running" && <span className="inline-block w-2 h-3.5 bg-green-400 animate-pulse ml-0.5" />}<div ref={bottomRef} /></div>{run.error && <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700">{run.error}</div>}{run.result && <details className="text-xs"><summary className="cursor-pointer text-gray-500 hover:text-gray-700">{"\uacb0\uacfc JSON \ubcf4\uae30"}</summary><pre className="mt-2 bg-gray-50 rounded p-3 overflow-x-auto text-gray-700 text-[11px]">{JSON.stringify(run.result, null, 2)}</pre></details>}</div>;
}
