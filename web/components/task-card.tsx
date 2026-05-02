"use client";

import { useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { startRun } from "@/lib/api";
import { cn, categoryBadge, categoryColor, getCategoryFromId } from "@/lib/utils";
import { Button } from "./ui/button";
import { RunStatusBadge } from "./run-status-badge";
import type { ExecutionMode, IntegrationRun, IntegrationTaskSpec } from "@/lib/types";

const TASK_COPY: Record<string, { title: string; description: string }> = {
  "A-2": { title: "\uc791\ud488 \uc0ac\uc6a9 \uc2e0\uccad \uc2b9\uc778", description: "\ucc44\ub110\uc758 \uc791\ud488 \uc0ac\uc6a9 \uc694\uccad\uc744 \uac80\ud1a0\ud558\uace0 \uad8c\ud55c \uc2e0\uccad \ud750\ub984\uc744 \uc810\uac80\ud569\ub2c8\ub2e4." },
  "A-3": { title: "\ub124\uc774\ubc84 \ud074\ub9bd \uc6d4\ubcc4 \uc9d1\uacc4", description: "\ub124\uc774\ubc84 \ud074\ub9bd \uc2e0\uccad\uc790\uc640 \uc6d4\ubcc4 \uc9d1\uacc4 \ub370\uc774\ud130\ub97c \ud655\uc778\ud569\ub2c8\ub2e4." },
  "B-2": { title: "\ub124\uc774\ubc84 \ud074\ub9bd \uc131\uacfc\ubcf4\uace0", description: "\ud074\ub9bd \uc131\uacfc \ub370\uc774\ud130\ub97c \uc218\uc9d1\ud558\uace0 \uad8c\ub9ac\uc0ac\ubcc4 \ubcf4\uace0 \ud750\ub984\uc744 \uc810\uac80\ud569\ub2c8\ub2e4." },
  "C-1": { title: "\ub9ac\ub4dc \ubc1c\uad74", description: "\uc774\uc6a9 \ucc44\ub110\uc774 \ubd80\uc871\ud55c \uc601\uc0c1\uc744 \uae30\uc900\uc73c\ub85c \uc0c8 \ucc44\ub110 \ub9ac\ub4dc\ub97c \ucc3e\uc2b5\ub2c8\ub2e4." },
  "C-2": { title: "\ucf5c\ub4dc\uba54\uc77c \ubc1c\uc1a1", description: "\ub9ac\ub4dc \ucc44\ub110\uc5d0 \ubcf4\ub0bc \uc81c\uc548 \uba54\uc77c \ubc1c\uc1a1 \ud750\ub984\uc744 \uac80\uc99d\ud569\ub2c8\ub2e4." },
  "C-3": { title: "\uc2e0\uaddc \uc601\uc0c1 \ub4f1\ub85d", description: "\uc2e0\uaddc \uc601\uc0c1\uacfc \uad8c\ub9ac\uc0ac \uc815\ubcf4\ub97c \ub4f1\ub85d\ud558\ub294 \ud750\ub984\uc744 \uc810\uac80\ud569\ub2c8\ub2e4." },
  "C-4": { title: "\ucfe0\ud3f0 \uc694\uccad \uc54c\ub9bc", description: "\ucc44\ub110\uc758 \ucfe0\ud3f0 \uc694\uccad\uc744 \uc778\uc2dd\ud558\uace0 \uad00\ub9ac\uc790 \uc54c\ub9bc \ud750\ub984\uc744 \ud655\uc778\ud569\ub2c8\ub2e4." },
  "D-2": { title: "\uad8c\ub9ac \uc18c\uba85 \uc694\uccad", description: "\uad8c\ub9ac \uc18c\uba85 \uc694\uccad\uc744 \uc811\uc218\ud558\uace0 \uad8c\ub9ac\uc0ac \uba54\uc77c \ud750\ub984\uc744 \uac80\ud1a0\ud569\ub2c8\ub2e4." },
  "D-3": { title: "\uce74\uce74\uc624 \ud06c\ub9ac\uc5d0\uc774\ud130 \uc628\ubcf4\ub529", description: "\uce74\uce74\uc624 \ud06c\ub9ac\uc5d0\uc774\ud130 \uc2e0\uccad\uc790 \uc628\ubcf4\ub529 \ud750\ub984\uc744 \uc810\uac80\ud569\ub2c8\ub2e4." },
};

const LINK_LABELS: Record<string, string> = {
  "\ub85c\uadf8\uc2dc\ud2b8": "\ub85c\uadf8",
};

function taskTitle(task: IntegrationTaskSpec) {
  return TASK_COPY[task.task_id]?.title ?? task.title.replace(/^[A-Z]-\d+\s+/, "");
}

function taskDescription(task: IntegrationTaskSpec) {
  return TASK_COPY[task.task_id]?.description ?? task.description;
}

export function TaskCard({ task, latestRun, onRunStarted }: { task: IntegrationTaskSpec; latestRun?: IntegrationRun | null; onRunStarted?: (run: IntegrationRun) => void }) {
  const cat = getCategoryFromId(task.task_id);
  const [payload, setPayload] = useState(JSON.stringify(task.default_payload, null, 2));
  const [approved, setApproved] = useState(false);
  const [payloadError, setPayloadError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();
  const { mutate, isPending } = useMutation({
    mutationFn: ({ mode, approvedFlag }: { mode: ExecutionMode; approvedFlag: boolean }) => {
      let parsed: Record<string, unknown>;
      try { parsed = JSON.parse(payload); } catch { throw new Error("Payload JSON \ud30c\uc2f1\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4."); }
      return startRun(task.task_id, parsed, mode, approvedFlag);
    },
    onSuccess: (run) => { qc.invalidateQueries({ queryKey: ["runs"] }); onRunStarted?.(run); },
    onError: (e: Error) => setPayloadError(e.message),
  });
  const handleRun = useCallback((mode: ExecutionMode) => {
    setPayloadError("");
    try { JSON.parse(payload); } catch { setPayloadError("\uc720\ud6a8\ud55c JSON\uc774 \uc544\ub2d9\ub2c8\ub2e4."); return; }
    mutate({ mode, approvedFlag: approved });
  }, [approved, mutate, payload]);
  const relatedLinks = Object.entries(task.sheet_links ?? {}).filter(([, v]) => v);
  return <article className={cn("rounded-xl border bg-gradient-to-br shadow-sm overflow-hidden", categoryColor[cat] ?? "from-gray-50 to-gray-100 border-gray-200")}><div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/60"><span className={cn("rounded-md px-2 py-0.5 text-xs font-bold", categoryBadge[cat] ?? "bg-gray-600 text-white")}>{task.task_id}</span><h3 className="flex-1 font-semibold text-sm text-gray-800 leading-tight">{taskTitle(task)}</h3>{latestRun && <RunStatusBadge status={latestRun.status} />}<button type="button" onClick={() => setExpanded((v) => !v)} className="text-gray-400 hover:text-gray-600" aria-label={expanded ? "\uc811\uae30" : "\ud3bc\uce58\uae30"}>{expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</button></div><div className="p-4 space-y-3 bg-white/70"><p className="text-xs text-gray-600 leading-relaxed whitespace-pre-wrap line-clamp-3">{taskDescription(task)}</p><div className="flex flex-wrap gap-1.5">{task.targets.map((t) => <span key={t} className="text-[11px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">{t}</span>)}{task.requires_approval && <span className="text-[11px] bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 font-medium">{"\uc2b9\uc778 \ud544\uc694"}</span>}</div>{relatedLinks.length > 0 && <div className="flex flex-wrap gap-1.5">{relatedLinks.map(([name, url]) => <a key={name} href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[11px] bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-full px-2.5 py-0.5">{LINK_LABELS[name] ?? name}<ExternalLink size={10} /></a>)}</div>}{expanded && <div className="space-y-3 pt-1 border-t border-gray-100">{task.real_run_warning && <div className="flex gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3"><AlertTriangle size={14} className="text-amber-500 flex-shrink-0 mt-0.5" /><p className="text-xs text-amber-800 whitespace-pre-wrap">{task.real_run_warning}</p></div>}<div><label className="block text-[11px] text-gray-500 mb-1 font-medium uppercase tracking-wide">Payload</label><textarea value={payload} onChange={(e) => { setPayload(e.target.value); setPayloadError(""); }} rows={Math.min(12, payload.split("\n").length + 1)} className="w-full rounded-lg border border-gray-200 bg-gray-900 text-green-300 font-mono text-[11px] px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y" spellCheck={false} />{payloadError && <p className="text-xs text-red-600 mt-1">{payloadError}</p>}</div>{task.requires_approval && <label className="flex items-center gap-2 text-xs text-gray-700 cursor-pointer"><input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />{"\uc2e4\ud589 \uc2b9\uc778"}</label>}<div className="flex gap-2 justify-end">{task.supports_dry_run && <Button variant="ghost" size="sm" loading={isPending} onClick={() => handleRun("dry_run")}>Dry Run</Button>}<Button variant="primary" size="sm" loading={isPending} onClick={() => handleRun("real_run")}>Real Run</Button></div></div>}{!expanded && <div className="flex gap-2 justify-end">{task.supports_dry_run && <Button variant="ghost" size="sm" loading={isPending} onClick={() => handleRun("dry_run")}>Dry Run</Button>}<Button variant="primary" size="sm" loading={isPending} onClick={() => setExpanded(true)}>{"\uc2e4\ud589"}</Button></div>}</div></article>;
}
