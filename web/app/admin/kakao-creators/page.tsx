"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchKakaoCreators, type KakaoCreator } from "@/lib/api";
import { CACHE_SEMI_STATIC } from "@/lib/query-client";

const STATUS_COLOR: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  inactive: "bg-slate-100 text-slate-500",
  pending: "bg-amber-100 text-amber-700",
};

const STATUS_LABEL: Record<string, string> = {
  active: "활성",
  inactive: "비활성",
  pending: "대기",
};

const columns: Array<{
  key: string;
  label: string;
  render: (creator: KakaoCreator) => ReactNode;
}> = [
  { key: "batch_number", label: "입점 차수", render: (c) => text(c.batch_number ?? c.onboarding_round) },
  { key: "partner_name", label: "제휴사명", render: (c) => text(c.partner_name) },
  { key: "is_active", label: "운영 여부", render: (c) => flag(c.is_active, c.operation_enabled) },
  { key: "is_whitelisted", label: "화이트리스트 사용 여부", render: (c) => flag(c.is_whitelisted, c.whitelist_enabled) },
  { key: "creator_name", label: "크리에이터명", render: (c) => <span className="font-medium text-slate-900">{text(c.creator_name)}</span> },
  { key: "is_crawled", label: "크롤링 수집", render: (c) => flag(c.is_crawled, c.crawling_collection ? "O" : null) },
  { key: "kakao_channel_name", label: "카카오톡 채널명", render: (c) => text(c.kakao_channel_name ?? c.channel_name ?? c.kakao_channel) },
  { key: "kakao_email", label: "카카오 email 주소", render: (c) => text(c.kakao_email ?? c.contact_email) },
  { key: "account_type", label: "계정 유형", render: (c) => text(c.account_type) },
  { key: "channel_link", label: "채널 링크", render: (c) => link(c.channel_link) },
  { key: "youtube_channel_id", label: "유튜브 채널 ID", render: (c) => text(c.youtube_channel_id) },
  { key: "subscriber_count", label: "구독자 수", render: (c) => numberText(c.subscriber_count) },
  { key: "scale", label: "규모", render: (c) => text(c.scale) },
  { key: "category", label: "카테고리", render: (c) => text(c.category) },
  { key: "sub_category", label: "세부 카테고리", render: (c) => text(c.sub_category) },
  { key: "account_classification", label: "계정 구분", render: (c) => text(c.account_classification) },
  { key: "is_linked", label: "연동 여부", render: (c) => flag(c.is_linked, c.sync_enabled ?? c.youtube_kakao_sync_wanted) },
  { key: "jjal_studio_id", label: "짤스튜디오ID", render: (c) => text(c.jjal_studio_id ?? c.zzalstudio_id) },
  { key: "is_onboarded", label: "온보딩 완료", render: (c) => flag(c.is_onboarded, c.onboarding_completed) },
  { key: "permission_status", label: "권한 상태", render: (c) => text(c.permission_status) },
  { key: "remarks", label: "비고", render: (c) => text(c.remarks ?? c.note) },
];

function text(value: unknown) {
  const normalized = String(value ?? "").trim();
  return normalized || "-";
}

function numberText(value?: number | null) {
  return typeof value === "number" ? value.toLocaleString("ko-KR") : "-";
}

function flag(value?: boolean | null, fallback?: string | null) {
  if (typeof value === "boolean") return value ? "O" : "X";
  return text(fallback);
}

function link(value?: string | null) {
  const href = String(value ?? "").trim();
  if (!href) return "-";
  return (
    <a className="text-blue-600 hover:underline" href={href} target="_blank" rel="noreferrer">
      {href}
    </a>
  );
}

export default function KakaoCreatorsPage() {
  const [statusFilter, setStatusFilter] = useState("all");

  const query = useQuery<{ items: KakaoCreator[] }>({
    queryKey: ["kakao-creators"],
    queryFn: fetchKakaoCreators,
    ...CACHE_SEMI_STATIC,
  });

  const all = query.data?.items ?? [];
  const creators = statusFilter === "all" ? all : all.filter((c) => c.status === statusFilter);

  return (
    <div className="p-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Supabase kakao_creators LIST</h1>
          <p className="mt-1 text-sm text-slate-500">
            Supabase kakao_creators 테이블의 속성을 한국어 컬럼명으로 표시합니다.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
          {["all", "active", "pending", "inactive"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === s
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {s === "all" ? "전체" : STATUS_LABEL[s] ?? s}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-slate-400">불러오는 중...</div>
        )}
        {query.isError && (
          <div className="p-8 text-center text-sm text-red-500">
            오류: {(query.error as Error).message}
          </div>
        )}
        {!query.isLoading && !query.isError && (
          <table className="min-w-[2200px] w-full text-sm">
            <thead className="bg-slate-50">
              <tr className="border-b border-slate-200">
                {columns.map((column) => (
                  <th key={column.key} className="px-4 py-3.5 text-left text-xs font-semibold text-slate-500">
                    {column.label}
                  </th>
                ))}
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-500">상태</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {creators.length === 0 && (
                <tr>
                  <td colSpan={columns.length + 1} className="px-5 py-12 text-center text-slate-400">
                    해당 크리에이터가 없습니다.
                  </td>
                </tr>
              )}
              {creators.map((creator) => (
                <tr key={creator.id} className="transition-colors hover:bg-slate-50/60">
                  {columns.map((column) => (
                    <td key={column.key} className="max-w-[220px] px-4 py-3.5 text-slate-600">
                      <div className="truncate" title={String(column.render(creator) ?? "")}>
                        {column.render(creator)}
                      </div>
                    </td>
                  ))}
                  <td className="px-4 py-3.5">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        STATUS_COLOR[creator.status] ?? "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {STATUS_LABEL[creator.status] ?? creator.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!query.isLoading && all.length > 0 && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
          <p>Source: Supabase public.kakao_creators</p>
          <p>전체 {all.length}명 중 {creators.length}명 표시</p>
        </div>
      )}
    </div>
  );
}
