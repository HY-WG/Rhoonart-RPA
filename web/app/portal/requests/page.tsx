"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle, Clock, FileText, PlayCircle, XCircle } from "lucide-react";
import { fetchMyWorkRequests } from "@/lib/api";
import type { WorkRequest } from "@/lib/types";

const statusMeta = {
  pending: { label: "처리 중", icon: Clock, cls: "text-amber-700 bg-amber-50" },
  approved: { label: "승인 완료", icon: CheckCircle, cls: "text-emerald-700 bg-emerald-50" },
  rejected: { label: "반려", icon: XCircle, cls: "text-red-600 bg-red-50" },
} as const;

function getStatusMeta(status: WorkRequest["status"]) {
  if (status === "approved" || status === "rejected") return statusMeta[status];
  return statusMeta.pending;
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RequestsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["my-work-requests"],
    queryFn: fetchMyWorkRequests,
    staleTime: 30_000,
  });
  const requests = data?.items ?? [];

  return (
    <div className="max-w-4xl p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <FileText className="h-6 w-6 text-indigo-600" />
            작품 사용 신청 진행 현황
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            내 채널의 영상권한 신청 내역을 백엔드 API에서 불러옵니다.
          </p>
        </div>
        <Link
          href="/portal"
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          <PlayCircle className="h-4 w-4" />
          내 채널에서 신청하기
        </Link>
      </div>

      {isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          신청 내역을 불러오는 중입니다.
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
          오류: {(error as Error).message}
        </div>
      )}

      {!isLoading && !error && requests.length === 0 && (
        <div className="flex h-56 flex-col items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white text-slate-500">
          <FileText className="h-9 w-9 opacity-40" />
          <p className="text-sm">아직 접수된 영상권한 신청 내역이 없습니다.</p>
          <Link href="/portal" className="text-sm font-medium text-indigo-600 hover:underline">
            내 채널에서 첫 신청 진행하기
          </Link>
        </div>
      )}

      <div className="space-y-3">
        {requests.map((req) => {
          const meta = getStatusMeta(req.status);
          const Icon = meta.icon;
          const [textClass, bgClass] = meta.cls.split(" ");

          return (
            <article
              key={req.id}
              className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-start gap-4">
                <div className={`rounded-lg p-2 ${bgClass}`}>
                  <Icon className={`h-4 w-4 ${textClass}`} />
                </div>
                <div>
                  <p className="font-medium text-slate-900">{req.work_title}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    신청일: {formatDate(req.requested_at)}
                    {req.processed_at ? ` | 처리일: ${formatDate(req.processed_at)}` : ""}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {req.channel_name || "채널명 미입력"}
                    {req.creator_email ? ` | ${req.creator_email}` : ""}
                  </p>
                  {req.status === "rejected" && req.rejection_message && (
                    <p className="mt-2 max-w-2xl rounded-lg bg-red-50 px-3 py-2 text-xs leading-5 text-red-600">
                      {req.rejection_message}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${meta.cls}`}>
                  {meta.label}
                </span>
                {req.status === "approved" && req.drive_link && (
                  <a
                    href={req.drive_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-indigo-600 hover:underline"
                  >
                    파일 열기
                  </a>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
