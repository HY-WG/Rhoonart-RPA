"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Settings } from "lucide-react";

interface RightsHolderReport {
  id: string;
  name: string;
  embed_url: string;
  configured: boolean;
}

interface MetabaseReport {
  title: string;
  embed_url: string;
  configured: boolean;
  env_key: string;
  reports: RightsHolderReport[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function fetchMetabaseReport(): Promise<MetabaseReport> {
  return fetch(`${API_BASE}/api/admin/reports/metabase`)
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });
}

export default function NaverClipReportPage() {
  const [selectedId, setSelectedId] = useState<string>("");
  const query = useQuery<MetabaseReport>({
    queryKey: ["metabase-report"],
    queryFn: fetchMetabaseReport,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!selectedId && query.data?.reports.length) {
      setSelectedId(query.data.reports[0].id);
    }
  }, [query.data?.reports, selectedId]);

  const selectedReport = useMemo(() => {
    if (!query.data?.reports.length) return null;
    return query.data.reports.find((r) => r.id === selectedId) ?? query.data.reports[0];
  }, [query.data?.reports, selectedId]);

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="mx-auto max-w-7xl">
        {/* 헤더 */}
        <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-widest text-blue-600 uppercase">Metabase</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900">네이버 클립 성과 확인</h1>
            <p className="mt-1 text-sm text-slate-500">
              권리사를 선택하면 해당 Metabase 대시보드를 페이지 안에서 확인합니다.
            </p>
          </div>
          {selectedReport?.embed_url && (
            <a
              href={selectedReport.embed_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:border-blue-400 hover:text-blue-700 transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
              새 창에서 열기
            </a>
          )}
        </div>

        {/* 로딩 */}
        {query.isLoading && (
          <div className="mt-8 rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
            대시보드 정보를 불러오는 중…
          </div>
        )}

        {/* 에러 */}
        {query.isError && (
          <div className="mt-8 rounded-xl border border-red-200 bg-red-50 p-8 text-sm text-red-600">
            오류: {(query.error as Error).message}
          </div>
        )}

        {query.data && (
          <div className="mt-6">
            {/* 권리사 탭 */}
            {query.data.reports.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {query.data.reports.map((report) => {
                  const active = report.id === selectedReport?.id;
                  return (
                    <button
                      key={report.id}
                      type="button"
                      onClick={() => setSelectedId(report.id)}
                      className={[
                        "h-9 rounded-lg border px-5 text-sm font-medium transition-colors",
                        active
                          ? "border-blue-600 bg-blue-600 text-white shadow-sm"
                          : "border-slate-300 bg-white text-slate-600 hover:border-blue-400 hover:text-blue-700",
                      ].join(" ")}
                    >
                      {report.name}
                    </button>
                  );
                })}
              </div>
            )}

            {/* URL 미설정 안내 */}
            {!query.data.configured && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
                <div className="flex items-start gap-3">
                  <Settings className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-semibold text-amber-800">Metabase URL이 설정되지 않았습니다.</p>
                    <p className="mt-1 text-sm text-amber-700">
                      백엔드 실행 환경의{" "}
                      <code className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs">
                        {query.data.env_key}
                      </code>{" "}
                      에 Metabase 공개 임베드 URL을 설정해주세요.
                    </p>
                    <p className="mt-2 text-xs text-amber-600">
                      Metabase 대시보드 → 공유 → 공개 URL 또는 임베드 URL 복사 후 .env에 추가
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* iframe */}
            {selectedReport?.configured && selectedReport.embed_url && (
              <div className="h-[720px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <iframe
                  title={`${query.data.title} - ${selectedReport.name}`}
                  src={selectedReport.embed_url}
                  className="h-full w-full"
                  allowFullScreen
                />
              </div>
            )}

            {/* 권리사 없음 */}
            {query.data.reports.length === 0 && query.data.configured && (
              <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
                표시할 권리사가 없습니다. Supabase의 rights_holders 테이블을 확인해주세요.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
