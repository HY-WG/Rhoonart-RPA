"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchResources } from "@/lib/api";
import { ExternalLink } from "lucide-react";

export default function ResourcesPage() {
  const { data: resources, isLoading } = useQuery({
    queryKey: ["resources"],
    queryFn: fetchResources,
    staleTime: 30_000,
  });

  const fields = resources
    ? [
        { label: "Google 인증 파일", value: resources.google_credentials_file },
        { label: "콘텐츠 시트 ID", value: resources.content_sheet_id },
        { label: "리드 시트 ID", value: resources.lead_sheet_id },
        { label: "로그 시트 ID", value: resources.log_sheet_id },
        { label: "발신자 이메일", value: resources.sender_email },
        { label: "Slack 에러 채널", value: resources.slack_error_channel },
        { label: "DB 타입", value: resources.dashboard_repository },
        {
          label: "Supabase 연결",
          value: resources.supabase_configured ? "✅ 연결됨" : "❌ 미연결",
        },
      ]
    : [];

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">환경 요약</h2>
        <p className="text-sm text-gray-400 mt-0.5">
          현재 대시보드가 바라보는 주요 자원과 연결 상태입니다.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm divide-y divide-gray-50">
            {fields.map((f) => (
              <div key={f.label} className="flex items-center px-5 py-3 gap-4">
                <span className="text-xs text-gray-500 w-40 flex-shrink-0">
                  {f.label}
                </span>
                <span className="text-sm text-gray-800 font-mono truncate">
                  {f.value || "—"}
                </span>
              </div>
            ))}
          </div>

          {/* 등록된 태스크 */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="font-semibold text-sm text-gray-900">
                등록된 태스크 ({resources?.tasks.length ?? 0}개)
              </h3>
            </div>
            <div className="divide-y divide-gray-50">
              {(resources?.tasks ?? []).map((t) => (
                <div
                  key={t.task_id}
                  className="flex items-center px-5 py-3 gap-3"
                >
                  <span className="text-xs font-bold bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">
                    {t.task_id}
                  </span>
                  <span className="flex-1 text-sm text-gray-700">{t.title}</span>
                  <div className="flex gap-1">
                    {Object.entries(t.sheet_links ?? {}).map(([name, url]) =>
                      url ? (
                        <a
                          key={name}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[10px] bg-gray-100 hover:bg-gray-200 text-gray-500 rounded px-1.5 py-0.5 transition-colors"
                        >
                          {name}
                          <ExternalLink size={9} />
                        </a>
                      ) : null
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
