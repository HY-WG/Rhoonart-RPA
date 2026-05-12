"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSeedChannels, type SeedChannel } from "@/lib/api";
import { CACHE_SEMI_STATIC } from "@/lib/query-client";

const PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  naver: "네이버",
  kakao: "카카오",
};

const STATUS_COLOR: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  inactive: "bg-slate-100 text-slate-500",
  pending: "bg-amber-100 text-amber-700",
};

export default function AdminChannelsPage() {
  const query = useQuery<{ items: SeedChannel[] }>({
    queryKey: ["seed-channels"],
    queryFn: () => fetchSeedChannels(),
    ...CACHE_SEMI_STATIC,
  });

  const channels = query.data?.items ?? [];

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">채널 관리</h1>
        <p className="mt-1 text-sm text-slate-500">
          등록된 시드 채널의 운영 상태를 확인합니다.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-slate-400">채널을 불러오는 중입니다…</div>
        )}
        {query.isError && (
          <div className="p-8 text-center text-sm text-red-500">
            오류: {(query.error as Error).message}
          </div>
        )}
        {!query.isLoading && !query.isError && (
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-slate-50">
              <tr className="border-b border-slate-200">
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">채널명</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">채널 ID</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">플랫폼</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">유형</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">담당자</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">상태</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-slate-500">URL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {channels.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-400">
                    등록된 채널이 없습니다.
                  </td>
                </tr>
              )}
              {channels.map((ch, idx) => (
                <tr key={ch.channel_id ?? idx} className="hover:bg-slate-50/60 transition-colors">
                  <td className="px-5 py-3.5 font-medium text-slate-900">
                    {ch.channel_title ?? ch.channel_id ?? "-"}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">
                    {ch.channel_id ?? "-"}
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">
                    {PLATFORM_LABEL[ch.platform ?? ""] ?? ch.platform ?? "-"}
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{ch.type ?? "-"}</td>
                  <td className="px-5 py-3.5 text-slate-600">{ch.managed_by ?? "-"}</td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        STATUS_COLOR[ch.status ?? ""] ?? "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {ch.status ?? "-"}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    {ch.channel_url ? (
                      <a
                        href={ch.channel_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="max-w-[200px] truncate text-teal-600 hover:underline block"
                        title={ch.channel_url}
                      >
                        {ch.channel_url}
                      </a>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
