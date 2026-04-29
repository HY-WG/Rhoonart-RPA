import { createClient } from "@/lib/supabase/server";
import { getUser } from "@/lib/auth";
import { FileText, Clock, CheckCircle, XCircle } from "lucide-react";

type WorkRequest = {
  id: string;
  work_title: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  processed_at: string | null;
  drive_link: string | null;
};

async function getMyRequests(): Promise<WorkRequest[]> {
  const supabase = await createClient();
  const user = await getUser();
  if (!user) return [];

  const { data, error } = await supabase
    .from("work_requests")
    .select("id, work_title, status, requested_at, processed_at, drive_link")
    .eq("creator_id", user.id)
    .order("requested_at", { ascending: false });

  if (error) return [];
  return (data ?? []) as WorkRequest[];
}

export default async function RequestsPage() {
  const requests = await getMyRequests().catch(() => [] as WorkRequest[]);

  const statusMeta = {
    pending: {
      label: "처리 중",
      icon: Clock,
      className: "text-amber-600 bg-amber-50",
    },
    approved: {
      label: "승인됨",
      icon: CheckCircle,
      className: "text-emerald-600 bg-emerald-50",
    },
    rejected: {
      label: "거절됨",
      icon: XCircle,
      className: "text-red-500 bg-red-50",
    },
  };

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <FileText className="w-6 h-6 text-indigo-500" />
          작품 사용 신청 현황
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          신청한 작품 사용 요청 {requests.length}건
        </p>
      </div>

      <div className="space-y-3">
        {requests.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center h-48 text-slate-400 gap-2">
            <FileText className="w-8 h-8 opacity-30" />
            <p className="text-sm">신청 내역이 없습니다.</p>
          </div>
        ) : (
          requests.map((req) => {
            const meta = statusMeta[req.status];
            const Icon = meta.icon;
            return (
              <div
                key={req.id}
                className="bg-white rounded-xl border border-slate-200 px-5 py-4 flex items-center justify-between"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`p-2 rounded-lg ${meta.className.split(" ")[1]}`}
                  >
                    <Icon
                      className={`w-4 h-4 ${meta.className.split(" ")[0]}`}
                    />
                  </div>
                  <div>
                    <p className="font-medium text-slate-800 text-sm">
                      {req.work_title}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      신청일:{" "}
                      {new Date(req.requested_at).toLocaleDateString("ko-KR")}
                      {req.processed_at && (
                        <>
                          {" "}
                          · 처리일:{" "}
                          {new Date(req.processed_at).toLocaleDateString(
                            "ko-KR"
                          )}
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-medium ${meta.className}`}
                  >
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
          })
        )}
      </div>
    </div>
  );
}
