"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createClient } from "@/lib/supabase/client";
import { FileText, Clock, CheckCircle, XCircle, PlusCircle } from "lucide-react";

// ── 타입 ──────────────────────────────────────────────────────────────────────
type WorkRequest = {
  id: string;
  work_title: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  processed_at: string | null;
  drive_link: string | null;
};

const statusMeta = {
  pending: { label: "처리 중", icon: Clock, cls: "text-amber-600 bg-amber-50" },
  approved: { label: "승인됨", icon: CheckCircle, cls: "text-emerald-600 bg-emerald-50" },
  rejected: { label: "거절됨", icon: XCircle, cls: "text-red-500 bg-red-50" },
} as const;

// ── 훅 ───────────────────────────────────────────────────────────────────────
async function fetchMyRequests(): Promise<WorkRequest[]> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];

  const { data, error } = await supabase
    .from("work_requests")
    .select("id, work_title, status, requested_at, processed_at, drive_link")
    .eq("creator_id", user.id)
    .order("requested_at", { ascending: false });

  if (error) throw new Error(error.message);
  return (data ?? []) as WorkRequest[];
}

async function submitWorkRequest(workTitle: string): Promise<void> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error("로그인이 필요합니다.");

  const { error } = await supabase.from("work_requests").insert({
    creator_id: user.id,
    work_title: workTitle.trim(),
    status: "pending",
  });
  if (error) throw new Error(error.message);
}

// ── 신청 폼 ──────────────────────────────────────────────────────────────────
function RequestForm({ onClose }: { onClose: () => void }) {
  const [workTitle, setWorkTitle] = useState("");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const qc = useQueryClient();

  const submit = useMutation({
    mutationFn: () => submitWorkRequest(workTitle),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-work-requests"] });
      setResult({ ok: true, msg: `"${workTitle}" 신청이 접수되었습니다.` });
      setWorkTitle("");
    },
    onError: (e: Error) => setResult({ ok: false, msg: e.message }),
  });

  return (
    <div className="bg-white rounded-xl border border-indigo-200 p-5 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-indigo-700">새 작품 사용 신청</h3>
        <button onClick={onClose} className="text-xs text-slate-400 hover:text-slate-600">닫기 ×</button>
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}
        className="flex items-end gap-3"
      >
        <div className="flex-1 flex flex-col gap-1">
          <label className="text-xs text-slate-500">작품명</label>
          <input
            required
            value={workTitle}
            onChange={(e) => setWorkTitle(e.target.value)}
            placeholder="예: 21세기 대군부인"
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
        <button
          type="submit"
          disabled={submit.isPending || !workTitle.trim()}
          className="px-5 py-2 bg-indigo-500 text-white text-sm font-medium rounded-lg hover:bg-indigo-600 disabled:opacity-50"
        >
          {submit.isPending ? "접수 중…" : "신청"}
        </button>
      </form>
      {result && (
        <p className={`mt-2 text-sm ${result.ok ? "text-emerald-600" : "text-red-500"}`}>
          {result.ok ? "✓ " : "✗ "}{result.msg}
        </p>
      )}
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────
export default function RequestsPage() {
  const [showForm, setShowForm] = useState(false);

  const { data: requests = [], isLoading, error } = useQuery<WorkRequest[]>({
    queryKey: ["my-work-requests"],
    queryFn: fetchMyRequests,
    staleTime: 30_000,
  });

  return (
    <div className="p-8 max-w-3xl">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <FileText className="w-6 h-6 text-indigo-500" />
            작품 사용 신청
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            총 {requests.length}건의 신청 내역
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 px-4 py-2 bg-indigo-500 text-white text-sm font-medium rounded-lg hover:bg-indigo-600"
        >
          <PlusCircle className="w-4 h-4" />
          새 신청
        </button>
      </div>

      {/* 신청 폼 */}
      {showForm && <RequestForm onClose={() => setShowForm(false)} />}

      {/* 목록 */}
      {isLoading && (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-sm text-slate-400">
          불러오는 중…
        </div>
      )}
      {error && (
        <div className="bg-red-50 rounded-xl border border-red-200 p-6 text-sm text-red-500">
          오류: {(error as Error).message}
        </div>
      )}

      <div className="space-y-3">
        {!isLoading && !error && requests.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center h-48 text-slate-400 gap-2">
            <FileText className="w-8 h-8 opacity-30" />
            <p className="text-sm">신청 내역이 없습니다.</p>
            <button
              onClick={() => setShowForm(true)}
              className="mt-2 text-sm text-indigo-500 hover:underline"
            >
              첫 번째 신청 하기 →
            </button>
          </div>
        )}

        {requests.map((req) => {
          const meta = statusMeta[req.status] ?? statusMeta.pending;
          const Icon = meta.icon;
          const [clrText, clrBg] = meta.cls.split(" ");

          return (
            <div
              key={req.id}
              className="bg-white rounded-xl border border-slate-200 px-5 py-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div className={`p-2 rounded-lg ${clrBg}`}>
                  <Icon className={`w-4 h-4 ${clrText}`} />
                </div>
                <div>
                  <p className="font-medium text-slate-800 text-sm">{req.work_title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    신청일: {new Date(req.requested_at).toLocaleDateString("ko-KR")}
                    {req.processed_at && (
                      <> · 처리일: {new Date(req.processed_at).toLocaleDateString("ko-KR")}</>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${meta.cls}`}>
                  {meta.label}
                </span>
                {req.status === "approved" && req.drive_link && (
                  <a
                    href={req.drive_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-indigo-500 hover:underline"
                  >
                    파일 열기 →
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
