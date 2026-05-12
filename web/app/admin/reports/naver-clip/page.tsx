"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Mail, RefreshCw, Settings } from "lucide-react";
import {
  fetchMetabaseReport,
  fetchLatestNaverSupabaseCollectJob,
  fetchNaverSupabaseCollectJob,
  sendMetabaseReport,
  startNaverSupabaseCollectJob,
} from "@/lib/api";
import { CACHE_DYNAMIC } from "@/lib/query-client";
import type { MetabaseRightsHolderReport, NaverCollectJob } from "@/lib/types";

const LAST_COLLECT_JOB_KEY = "naver-clip-last-collect-job-id";
const LAST_COLLECT_RUN_AT_KEY = "naver-clip-last-collect-run-at";

function uniqueReports(reports: MetabaseRightsHolderReport[]) {
  const seen = new Set<string>();
  return reports.filter((report) => {
    const name = report.name.trim();
    if (!name || seen.has(name)) return false;
    seen.add(name);
    return true;
  });
}

function reportEmail(report: MetabaseRightsHolderReport | null) {
  return report?.email || report?.mail || "";
}

function sortReports(reports: MetabaseRightsHolderReport[]) {
  return [...reports].sort((a, b) => {
    const enabledDiff =
      Number(Boolean(b.naver_report_enabled)) - Number(Boolean(a.naver_report_enabled));
    if (enabledDiff) return enabledDiff;
    return a.name.localeCompare(b.name, "ko");
  });
}

function isActiveJob(job?: NaverCollectJob) {
  return job?.status === "queued" || job?.status === "running";
}

function normalizeMetabaseUrl(url: string) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    const isLocalMetabaseDashboard =
      parsed.pathname.startsWith("/public/dashboard/") &&
      ["localhost", "127.0.0.1"].includes(parsed.hostname);
    if (isLocalMetabaseDashboard && parsed.port === "3001") {
      parsed.port = "3000";
      return parsed.toString();
    }
  } catch {
    return url;
  }
  return url;
}

function todayKst() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function withTodayMetabaseFilters(url: string) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    if (!parsed.pathname.startsWith("/public/dashboard/")) {
      return url;
    }
    const today = todayKst();
    parsed.searchParams.set("start_date", today);
    parsed.searchParams.set("end_date", today);
    return parsed.toString();
  } catch {
    return url;
  }
}

function formatLastCollectRunAt(value: string) {
  if (!value) return "기록 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.month}.${byType.day}. ${byType.hour}:${byType.minute}`;
}

export default function NaverClipReportPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>("");
  const [collectJobId, setCollectJobId] = useState<string>("");
  const [lastCollectRunAt, setLastCollectRunAt] = useState("");
  const [expiredJobMessage, setExpiredJobMessage] = useState("");

  useEffect(() => {
    setCollectJobId(window.localStorage.getItem(LAST_COLLECT_JOB_KEY) ?? "");
    setLastCollectRunAt(window.localStorage.getItem(LAST_COLLECT_RUN_AT_KEY) ?? "");
  }, []);

  const query = useQuery({
    queryKey: ["metabase-report"],
    queryFn: fetchMetabaseReport,
    ...CACHE_DYNAMIC,
  });

  const latestCollectJobQuery = useQuery({
    queryKey: ["naver-collect-job", "latest"],
    queryFn: fetchLatestNaverSupabaseCollectJob,
    ...CACHE_DYNAMIC,
  });

  const collectJobQuery = useQuery({
    queryKey: ["naver-collect-job", collectJobId],
    queryFn: () => fetchNaverSupabaseCollectJob(collectJobId),
    enabled: Boolean(collectJobId),
    refetchInterval: (queryState) => {
      const job = queryState.state.data;
      return isActiveJob(job) ? 2000 : false;
    },
  });

  const collectJob = collectJobQuery.data;
  const collectRunning = isActiveJob(collectJob);
  const latestCollectRunAt = collectJob?.finished_at || collectJob?.created_at || "";
  const persistedCollectRunAt =
    latestCollectJobQuery.data?.finished_at || latestCollectJobQuery.data?.created_at || "";
  const displayedLastCollectRunAt = latestCollectRunAt || persistedCollectRunAt || lastCollectRunAt;

  useEffect(() => {
    const message = (collectJobQuery.error as Error | null)?.message ?? "";
    if (!message.includes("collect job not found")) return;
    window.localStorage.removeItem(LAST_COLLECT_JOB_KEY);
    setCollectJobId("");
    setExpiredJobMessage(
      "이전 크롤링 작업 상태를 찾을 수 없습니다. 백엔드 재시작 등으로 작업 상태가 만료되었을 수 있습니다."
    );
  }, [collectJobQuery.error]);

  const { refetch: refetchQuery } = query;
  const { refetch: refetchLatestCollect } = latestCollectJobQuery;

  useEffect(() => {
    if (collectJob?.status === "completed") {
      void refetchQuery();
      void refetchLatestCollect();
    }
    if (!latestCollectRunAt) return;
    setLastCollectRunAt((prev) => {
      if (prev === latestCollectRunAt) return prev;
      window.localStorage.setItem(LAST_COLLECT_RUN_AT_KEY, latestCollectRunAt);
      return latestCollectRunAt;
    });
  }, [collectJob?.status, latestCollectRunAt, refetchQuery, refetchLatestCollect]);

  useEffect(() => {
    if (!persistedCollectRunAt) return;
    setLastCollectRunAt((prev) => {
      if (prev === persistedCollectRunAt) return prev;
      window.localStorage.setItem(LAST_COLLECT_RUN_AT_KEY, persistedCollectRunAt);
      return persistedCollectRunAt;
    });
  }, [persistedCollectRunAt]);

  const startCollectMutation = useMutation({
    mutationFn: () =>
      startNaverSupabaseCollectJob({
        triggered_by: "manual",
        max_clips_per_identifier: 2000,
      }),
    onSuccess: (job) => {
      setExpiredJobMessage("");
      setCollectJobId(job.job_id);
      const runAt = job.created_at || new Date().toISOString();
      setLastCollectRunAt(runAt);
      window.localStorage.setItem(LAST_COLLECT_JOB_KEY, job.job_id);
      window.localStorage.setItem(LAST_COLLECT_RUN_AT_KEY, runAt);
    },
  });

  const sendMutation = useMutation({
    mutationFn: (rightsHolderName: string) => sendMetabaseReport(rightsHolderName),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      void queryClient.invalidateQueries({ queryKey: ["metabase-report"] });
      void queryClient.invalidateQueries({ queryKey: ["naver-report-schedules"] });
    },
  });

  const reports = useMemo(
    () => sortReports(uniqueReports(query.data?.reports ?? [])),
    [query.data?.reports]
  );

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedId) ?? null,
    [reports, selectedId]
  );

  const selectedEmail = reportEmail(selectedReport);
  const selectedEmbedUrl = withTodayMetabaseFilters(
    normalizeMetabaseUrl(selectedReport?.embed_url ?? "")
  );
  const canSend = Boolean(
    selectedReport?.configured && selectedEmbedUrl && selectedEmail
  );
  const collectPercent = Math.max(0, Math.min(100, collectJob?.percent ?? 0));
  const collectButtonLabel =
    startCollectMutation.isPending || collectRunning
      ? "크롤링 진행 중"
      : "오늘자 크롤링";

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="mx-auto max-w-7xl">
        <div className="border-b border-slate-200 pb-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">
            Metabase
          </p>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">
            네이버 클립 성과 확인
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            권리사를 선택하면 해당 Metabase 대시보드를 페이지 안에서 확인합니다.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={startCollectMutation.isPending || collectRunning}
              onClick={() => {
                startCollectMutation.mutate();
              }}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
            >
              <RefreshCw
                className={[
                  "h-4 w-4",
                  startCollectMutation.isPending || collectRunning ? "animate-spin" : "",
                ].join(" ")}
              />
              {collectButtonLabel}
            </button>
            <p className="text-sm font-semibold text-red-600">
              마지막 시행: {formatLastCollectRunAt(displayedLastCollectRunAt)}
            </p>
            <p className="text-xs text-slate-500">
              버튼을 누르면 백엔드 작업으로 전환되어 다른 탭으로 이동해도 계속 진행됩니다.
            </p>
          </div>
        </div>

        {expiredJobMessage && (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            {expiredJobMessage}
          </div>
        )}

        {(collectJob || startCollectMutation.isPending || startCollectMutation.isError || (collectJobQuery.isError && collectJobId)) && (
          <section className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  오늘자 크롤링 진행 상태
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {startCollectMutation.isPending
                    ? "작업을 등록하는 중입니다."
                    : collectJob?.message ?? "작업 상태를 확인하는 중입니다."}
                </p>
                {collectJob?.run_id && (
                  <p className="mt-1 font-mono text-xs text-slate-400">
                    run_id: {collectJob.run_id}
                  </p>
                )}
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-slate-900">{collectPercent}%</p>
                <p className="text-xs text-slate-500">
                  {collectJob?.completed ?? 0}/{collectJob?.total ?? 0}
                </p>
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className={[
                  "h-full rounded-full transition-all",
                  collectJob?.status === "failed" ? "bg-red-500" : "bg-blue-600",
                ].join(" ")}
                style={{ width: `${collectPercent}%` }}
              />
            </div>
            {collectJob?.status === "completed" && (
              <p className="mt-3 text-sm text-emerald-700">
                완료되었습니다. 저장된 영상 수: {collectJob.row_count.toLocaleString()}
              </p>
            )}
            {(startCollectMutation.isError || (collectJobQuery.isError && collectJobId) || collectJob?.status === "failed") && (
              <p className="mt-3 text-sm text-red-600">
                {collectJob?.error_message ||
                  (startCollectMutation.error as Error | undefined)?.message ||
                  (collectJobQuery.error as Error | undefined)?.message}
              </p>
            )}
          </section>
        )}

        {query.isLoading && (
          <div className="mt-8 rounded-lg border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
            권리사 정보를 불러오는 중입니다.
          </div>
        )}

        {query.isError && (
          <div className="mt-8 rounded-lg border border-red-200 bg-red-50 p-8 text-sm text-red-600">
            오류: {(query.error as Error).message}
          </div>
        )}

        {query.data && (
          <div className="mt-6 space-y-5">
            <section className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">권리사</h2>
                  {selectedReport && (
                    <p className="mt-1 text-xs text-slate-500">
                      수신 메일:{" "}
                      {selectedEmail || "naver_rights_holders에 메일이 없습니다."}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedEmbedUrl && (
                    <a
                      href={selectedEmbedUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 transition-colors hover:border-blue-400 hover:text-blue-700"
                    >
                      <ExternalLink className="h-4 w-4" />새 창에서 열기
                    </a>
                  )}
                  <button
                    type="button"
                    disabled={!canSend || sendMutation.isPending}
                    onClick={() => {
                      if (selectedReport) {
                        sendMutation.mutate(selectedReport.name);
                      }
                    }}
                    className="inline-flex h-9 items-center gap-2 rounded-lg bg-slate-900 px-3 text-xs font-semibold text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    <Mail className="h-4 w-4" />
                    {sendMutation.isPending ? "발송 중" : "성과보고하기"}
                  </button>
                </div>
              </div>

              {reports.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {reports.map((report) => {
                    const active = report.id === selectedId;
                    const reportEnabled = Boolean(report.naver_report_enabled);
                    return (
                      <button
                        key={report.id}
                        type="button"
                        onClick={() => {
                          setSelectedId(report.id);
                          sendMutation.reset();
                        }}
                        className={[
                          "min-h-10 rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
                          active
                            ? "border-blue-600 bg-blue-600 text-white shadow-sm"
                            : reportEnabled
                              ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:border-emerald-500 hover:bg-emerald-100"
                              : "border-slate-300 bg-white text-slate-600 hover:border-blue-400 hover:text-blue-700",
                        ].join(" ")}
                      >
                        <span>{report.name}</span>
                        {reportEnabled && (
                          <span
                            className={[
                              "ml-2 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                              active ? "bg-white/20 text-white" : "bg-emerald-100 text-emerald-700",
                            ].join(" ")}
                          >
                            보고 활성
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-slate-400">
                  표시할 권리사가 없습니다. Supabase의 naver_rights_holders 테이블을
                  확인해주세요.
                </p>
              )}
            </section>

            {sendMutation.isSuccess && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                성과보고 메일을 발송했습니다:{" "}
                {sendMutation.data.recipients.join(", ")}
              </div>
            )}

            {sendMutation.isError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                메일 발송 실패: {(sendMutation.error as Error).message}
              </div>
            )}

            {!selectedReport && (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-16 text-center text-sm text-slate-400">
                권리사를 선택하면 Metabase 대시보드가 여기에 표시됩니다.
              </div>
            )}

            {selectedReport && !selectedReport.configured && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
                <div className="flex items-start gap-3">
                  <Settings className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                  <div className="text-sm text-amber-800">
                    <p className="font-semibold">
                      {selectedReport.name}의 Metabase embed URL이 아직 저장되지 않았습니다.
                    </p>
                    <p className="mt-1">
                      Supabase{" "}
                      <code className="rounded bg-amber-100 px-1 font-mono text-xs">
                        naver_rights_holders.metabase_embed_url
                      </code>
                      에 URL을 저장하거나, Metabase 대시보드 생성 스크립트를 실행해주세요.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {selectedReport?.configured && !selectedEmail && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                naver_rights_holders의 {selectedReport.name} 행에 email 또는 mail 값이
                없어 메일 발송을 할 수 없습니다.
              </div>
            )}

            {selectedReport?.configured && selectedEmbedUrl && (
              <div className="h-[760px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                <iframe
                  title={`${query.data.title} - ${selectedReport.name}`}
                  src={selectedEmbedUrl}
                  className="h-full w-full"
                  allowFullScreen
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
