"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { fetchMetabaseReport } from "@/lib/api";

export default function NaverClipReportPage() {
  const [selectedId, setSelectedId] = useState<string>("");
  const query = useQuery({ queryKey: ["metabase-report"], queryFn: fetchMetabaseReport });

  useEffect(() => {
    if (!selectedId && query.data?.reports.length) {
      setSelectedId(query.data.reports[0].id);
    }
  }, [query.data?.reports, selectedId]);

  const selectedReport = useMemo(() => {
    if (!query.data?.reports.length) {
      return null;
    }
    return query.data.reports.find((report) => report.id === selectedId) ?? query.data.reports[0];
  }, [query.data?.reports, selectedId]);

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-blue-700">{"METABASE"}</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">{"\ub124\uc774\ubc84 \ud074\ub9bd \uc131\uacfc \ud655\uc778"}</h1>
            <p className="mt-2 text-sm text-slate-500">{"\uad8c\ub9ac\uc0ac\ub97c \uc120\ud0dd\ud558\uba74 \ud574\ub2f9 METABASE \ud654\uba74\uc744 \ud398\uc774\uc9c0 \uc548\uc5d0\uc11c \ud655\uc778\ud569\ub2c8\ub2e4."}</p>
          </div>
          {selectedReport?.embed_url && (
            <a
              href={selectedReport.embed_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:border-blue-400 hover:text-blue-700"
            >
              <ExternalLink className="h-4 w-4" />
              {"\uc0c8 \ucc3d\uc5d0\uc11c \uc5f4\uae30"}
            </a>
          )}
        </div>

        {query.isLoading && (
          <div className="mt-6 rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
            {"\ud398\uc774\uc9c0 \uc815\ubcf4\ub97c \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."}
          </div>
        )}

        {query.isError && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-8 text-sm text-red-700">
            {(query.error as Error).message}
          </div>
        )}

        {query.data && (
          <div className="mt-6">
            <div className="flex flex-wrap gap-2">
              {query.data.reports.map((report) => {
                const active = report.id === selectedReport?.id;
                return (
                  <button
                    key={report.id}
                    type="button"
                    onClick={() => setSelectedId(report.id)}
                    className={[
                      "h-10 rounded-md border px-4 text-sm font-semibold transition",
                      active
                        ? "border-blue-600 bg-blue-600 text-white shadow-sm"
                        : "border-slate-300 bg-white text-slate-700 hover:border-blue-400 hover:text-blue-700",
                    ].join(" ")}
                  >
                    {report.name}
                  </button>
                );
              })}
            </div>

            {!selectedReport?.configured && (
              <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-8 text-sm text-amber-800">
                <p className="font-semibold">{"METABASE URL\uc774 \uc124\uc815\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4."}</p>
                <p className="mt-2 text-amber-700">
                  {"\ubc31\uc5d4\ub4dc \uc2e4\ud589 \ud658\uacbd\uc5d0 "}
                  <span className="font-mono font-semibold">{query.data.env_key}</span>
                  {"\uac12\uc744 public/embed \uac00\ub2a5\ud55c METABASE URL\ub85c \ucd94\uac00\ud574\uc8fc\uc138\uc694."}
                </p>
              </div>
            )}

            {selectedReport?.configured && selectedReport.embed_url && (
              <div className="mt-4 h-[680px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                <iframe title={`${query.data.title} - ${selectedReport.name}`} src={selectedReport.embed_url} className="h-full w-full" />
              </div>
            )}

            {query.data.reports.length === 0 && (
              <div className="mt-6 rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                {"\ud45c\uc2dc\ud560 \uad8c\ub9ac\uc0ac\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
