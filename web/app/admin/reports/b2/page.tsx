"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Database, RefreshCw } from "lucide-react";
import { collectB2SupabaseReports, fetchB2AnalyticsOptions, fetchB2ContentCatalog, fetchB2RightsHolders } from "@/lib/api";

function numberText(value: number | undefined) {
  return Number(value || 0).toLocaleString("ko-KR");
}

export default function B2SupabaseReportPage() {
  const queryClient = useQueryClient();
  const [maxClips, setMaxClips] = useState(2000);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const contentQuery = useQuery({ queryKey: ["b2-content-catalog"], queryFn: fetchB2ContentCatalog });
  const rightsQuery = useQuery({ queryKey: ["b2-rights-holders"], queryFn: fetchB2RightsHolders });
  const optionsQuery = useQuery({ queryKey: ["b2-analytics-options"], queryFn: fetchB2AnalyticsOptions });
  const collectMutation = useMutation({
    mutationFn: collectB2SupabaseReports,
    onSuccess: () => {
      setConfirmOpen(false);
      queryClient.invalidateQueries({ queryKey: ["b2-analytics-options"] });
    },
  });

  const enabledContents = useMemo(
    () => (contentQuery.data || []).filter((item) => item.naver_report_enabled || item.active_flag === "Active"),
    [contentQuery.data],
  );
  const enabledHolders = useMemo(
    () => (rightsQuery.data || []).filter((item) => item.naver_report_enabled),
    [rightsQuery.data],
  );
  const loading = contentQuery.isLoading || rightsQuery.isLoading || optionsQuery.isLoading;
  const error = contentQuery.error || rightsQuery.error || optionsQuery.error;

  return (
    <div className="p-8">
      <div className="mb-6 flex flex-col gap-4 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-700">{"B2 NAVER CLIP"}</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950">{"B2 Supabase \uc5c5\ub370\uc774\ud2b8"}</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            {"Supabase\uc5d0 \ub4f1\ub85d\ub41c B2 \uc791\ud488/\uad8c\ub9ac\uc0ac \ub300\uc0c1\uc744 \uae30\uc900\uc73c\ub85c \ub124\uc774\ubc84 \ud074\ub9bd \uc131\uacfc\ub97c \uc218\uc9d1\ud558\uace0 daily/history \ud14c\uc774\ube14\uc744 \uc5c5\ub370\uc774\ud2b8\ud569\ub2c8\ub2e4."}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setConfirmOpen(true)}
          disabled={loading || collectMutation.isPending}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400"
        >
          <RefreshCw className={`h-4 w-4 ${collectMutation.isPending ? "animate-spin" : ""}`} />
          {"Supabase \uc5c5\ub370\uc774\ud2b8 \uc2e4\ud589"}
        </button>
      </div>

      {loading && <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">{"B2 \uc124\uc815\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."}</div>}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-sm text-red-700">{(error as Error).message}</div>}

      {!loading && !error && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <article className="rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold text-slate-500">{"\uc5c5\ub370\uc774\ud2b8 \ub300\uc0c1 \uc791\ud488"}</p>
              <p className="mt-2 text-2xl font-bold text-slate-950">{numberText(enabledContents.length)}</p>
            </article>
            <article className="rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold text-slate-500">{"\uc131\uacfc\ubcf4\uace0 \ud65c\uc131 \uad8c\ub9ac\uc0ac"}</p>
              <p className="mt-2 text-2xl font-bold text-slate-950">{numberText(enabledHolders.length)}</p>
            </article>
            <article className="rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold text-slate-500">{"\uc800\uc7a5\ub41c \ud074\ub9bd \ud655\uc778\uc77c"}</p>
              <p className="mt-2 text-sm font-semibold text-slate-950">{optionsQuery.data?.checked_date_min || "-"}{" ~ "}{optionsQuery.data?.checked_date_max || "-"}</p>
            </article>
            <article className="rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold text-slate-500">{"\ucd5c\ub300 \uc218\uc9d1 \uac74\uc218"}</p>
              <label className="mt-2 flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={5000}
                  value={maxClips}
                  onChange={(event) => setMaxClips(Number(event.target.value || 1))}
                  className="h-9 w-full rounded-md border border-slate-300 px-3 text-sm"
                />
              </label>
            </article>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_360px]">
            <section className="rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-100 p-5">
                <h2 className="font-semibold text-slate-950">{"\uc218\uc9d1 \ub300\uc0c1 \uc791\ud488"}</h2>
                <p className="mt-1 text-sm text-slate-500">{"naver_report_enabled \ub610\ub294 Active \uc0c1\ud0dc\uc758 \uc791\ud488\uc785\ub2c8\ub2e4."}</p>
              </div>
              <div className="divide-y divide-slate-100">
                {enabledContents.length === 0 && <div className="p-8 text-center text-sm text-slate-500">{"\uc218\uc9d1 \ub300\uc0c1 \uc791\ud488\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."}</div>}
                {enabledContents.slice(0, 10).map((item) => (
                  <div key={`${item.content_name}-${item.identifier}`} className="grid grid-cols-[1fr_120px_160px] gap-4 p-4 text-sm">
                    <div>
                      <p className="font-semibold text-slate-900">{item.content_name}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.rights_holder_name || "-"}</p>
                    </div>
                    <p className="font-mono text-slate-600">{item.identifier}</p>
                    <p className="text-right text-slate-500">{item.naver_report_enabled ? "enabled" : item.active_flag || "-"}</p>
                  </div>
                ))}
              </div>
            </section>

            <aside className="space-y-4">
              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h2 className="font-semibold text-slate-950">{"\ud65c\uc131 \uad8c\ub9ac\uc0ac"}</h2>
                <div className="mt-4 space-y-3">
                  {enabledHolders.length === 0 && <p className="text-sm text-slate-500">{"\ud65c\uc131 \uad8c\ub9ac\uc0ac\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}</p>}
                  {enabledHolders.slice(0, 8).map((holder) => (
                    <div key={holder.rights_holder_name} className="rounded-md border border-slate-100 p-3">
                      <p className="text-sm font-semibold text-slate-900">{holder.rights_holder_name}</p>
                      <p className="mt-1 text-xs text-slate-500">{holder.email || "\uba54\uc77c \ubbf8\uc124\uc815"}</p>
                    </div>
                  ))}
                </div>
              </section>

              {collectMutation.data && (
                <section className="rounded-lg border border-green-200 bg-green-50 p-5">
                  <div className="flex items-center gap-2 text-green-800">
                    <CheckCircle2 className="h-5 w-5" />
                    <h2 className="font-semibold">{"\uc5c5\ub370\uc774\ud2b8 \uc644\ub8cc"}</h2>
                  </div>
                  <p className="mt-3 text-sm text-green-700">{"\uc800\uc7a5\ub41c \ud074\ub9bd"}: <strong>{numberText(collectMutation.data.row_count)}</strong></p>
                  <p className="mt-1 text-sm text-green-700">{"\ucd1d \uc870\ud68c\uc218"}: <strong>{numberText(collectMutation.data.summary.total_views)}</strong></p>
                </section>
              )}

              {collectMutation.isError && (
                <section className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
                  {(collectMutation.error as Error).message}
                </section>
              )}
            </aside>
          </div>
        </>
      )}

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-amber-100 p-2 text-amber-700">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-950">{"Supabase\uc5d0 B2 \uc218\uc9d1 \uacb0\uacfc\ub97c \uc800\uc7a5\ud560\uae4c\uc694?"}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {"\uc774 \uc791\uc5c5\uc740 \ub124\uc774\ubc84 \ud074\ub9bd \ub370\uc774\ud130\ub97c \uc218\uc9d1\ud558\uace0, \uc5f0\uacb0\ub41c Supabase\uc758 B2 daily/history \ud14c\uc774\ube14\uacfc \uc5f0\ub3c4 \uc9d1\uacc4\ub97c \uc5c5\ub370\uc774\ud2b8\ud569\ub2c8\ub2e4."}
                </p>
                <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                  <Database className="mr-2 inline h-4 w-4" />
                  {"\ub300\uc0c1 \uc791\ud488 "}
                  <strong>{enabledContents.length}</strong>
                  {", \ucd5c\ub300 \uc218\uc9d1 "}
                  <strong>{numberText(maxClips)}</strong>
                  {"\uac74/\uc791\ud488"}
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={() => setConfirmOpen(false)} className="h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                {"\ucde8\uc18c"}
              </button>
              <button
                type="button"
                disabled={collectMutation.isPending}
                onClick={() => collectMutation.mutate({ triggered_by: "manual", max_clips_per_identifier: maxClips })}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
              >
                <RefreshCw className={`h-4 w-4 ${collectMutation.isPending ? "animate-spin" : ""}`} />
                {"\uc5c5\ub370\uc774\ud2b8 \uc2e4\ud589"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
