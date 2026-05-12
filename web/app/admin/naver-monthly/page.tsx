"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import {
  downloadNaverMonthlyReportExcel,
  fetchNaverMonthlyReportConfig,
  triggerA3Report,
  updateNaverMonthlyReportManager,
} from "@/lib/api";

export default function NaverMonthlyPage() {
  const queryClient = useQueryClient();
  const [log, setLog] = useState<string[]>([]);
  const [editing, setEditing] = useState(false);
  const [managerName, setManagerName] = useState("");
  const [managerEmail, setManagerEmail] = useState("");

  const configQuery = useQuery({
    queryKey: ["naver-monthly-report-config"],
    queryFn: fetchNaverMonthlyReportConfig,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!configQuery.data) return;
    setManagerName(configQuery.data.manager.manager_name);
    setManagerEmail(configQuery.data.manager.manager_email);
  }, [configQuery.data]);

  const sendMutation = useMutation({
    mutationFn: triggerA3Report,
    onSuccess: (data) => {
      setLog((prev) => [
        `[${new Date().toLocaleTimeString("ko-KR")}] ${data.message ?? "완료"}`,
        ...prev,
      ]);
    },
    onError: (error) => {
      setLog((prev) => [
        `[${new Date().toLocaleTimeString("ko-KR")}] ${(error as Error).message}`,
        ...prev,
      ]);
    },
  });

  const managerMutation = useMutation({
    mutationFn: () =>
      updateNaverMonthlyReportManager({
        manager_name: managerName,
        manager_email: managerEmail,
      }),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["naver-monthly-report-config"] });
    },
  });

  const downloadMutation = useMutation({
    mutationFn: downloadNaverMonthlyReportExcel,
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `naver_inbound_${new Date().toISOString().slice(0, 7).replace("-", "")}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setLog((prev) => [
        `[${new Date().toLocaleTimeString("ko-KR")}] 엑셀 파일 다운로드를 시작했습니다.`,
        ...prev,
      ]);
    },
    onError: (error) => {
      setLog((prev) => [
        `[${new Date().toLocaleTimeString("ko-KR")}] 엑셀 다운로드 실패: ${(error as Error).message}`,
        ...prev,
      ]);
    },
  });

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">네이버 클립 채널 인입</h1>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
          현재 보이는 google spread sheet 의 데이터를 네이버 매니저에게 발송합니다.
          매월 말일 slack 으로 확인 메시지가 전송되며, 관리자가 별도 조취 취하지 않을시,
          보고 메일이 자동으로 생성되어 발송됩니다.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="rounded-xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">네이버 클립 채널 인입 보고용 Google Sheets</h2>
              <p className="mt-1 text-xs text-slate-500">
                Sheet1에서 인입 데이터를 일괄 관리합니다. 월별 시트는 자동 생성하지 않습니다.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => downloadMutation.mutate()}
                disabled={downloadMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
              >
                <Download className="h-3.5 w-3.5" />
                {downloadMutation.isPending ? "생성 중" : "다운로드"}
              </button>
              {configQuery.data?.sheet.url && (
                <a
                  href={configQuery.data.sheet.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:border-blue-400 hover:text-blue-700"
                >
                  새 창에서 열기
                </a>
              )}
            </div>
          </div>
          <div className="h-[620px] bg-slate-50">
            {configQuery.isLoading && (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                시트 정보를 불러오는 중입니다.
              </div>
            )}
            {configQuery.isError && (
              <div className="flex h-full items-center justify-center p-8 text-center text-sm text-red-500">
                {(configQuery.error as Error).message}
              </div>
            )}
            {configQuery.data?.sheet.embed_url && (
              <iframe
                title="네이버 클립 채널 인입 시트"
                src={configQuery.data.sheet.embed_url}
                className="h-full w-full"
              />
            )}
          </div>
        </section>

        <aside className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">보고 메일 발송</h2>
            <p className="mt-2 text-sm text-slate-500">
              매월 5일 메일이 자동 발송됩니다.
            </p>
            <button
              onClick={() => sendMutation.mutate()}
              disabled={sendMutation.isPending}
              className="mt-4 w-full rounded-lg bg-teal-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-600 disabled:opacity-50"
            >
              {sendMutation.isPending ? "보고 메일 생성 중" : "보고 메일 발송"}
            </button>

            <div className="mt-5 border-t border-slate-100 pt-5">
              <h3 className="text-sm font-semibold text-slate-900">관리자 정보</h3>
              <p className="mt-1 text-xs text-slate-400">
                이름 또는 이메일을 더블 클릭하면 바로 수정할 수 있습니다.
              </p>
              <div
                onDoubleClick={() => setEditing(true)}
                className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3"
              >
                {editing ? (
                  <div className="space-y-2">
                    <input
                      value={managerName}
                      onChange={(event) => setManagerName(event.target.value)}
                      className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                      placeholder="관리자 이름"
                    />
                    <input
                      value={managerEmail}
                      onChange={(event) => setManagerEmail(event.target.value)}
                      className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                      placeholder="관리자 이메일"
                    />
                    <button
                      type="button"
                      disabled={managerMutation.isPending}
                      onClick={() => managerMutation.mutate()}
                      className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-slate-300"
                    >
                      {managerMutation.isPending ? "저장 중" : "저장"}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-1 text-sm">
                    <p className="font-semibold text-slate-900">{managerName || "-"}</p>
                    <p className="text-slate-500">{managerEmail || "-"}</p>
                  </div>
                )}
              </div>
              {managerMutation.isError && (
                <p className="mt-2 text-xs text-red-500">
                  {(managerMutation.error as Error).message}
                </p>
              )}
            </div>
          </section>

          {log.length > 0 && (
            <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                실행 로그
              </p>
              <ul className="space-y-1">
                {log.map((line, index) => (
                  <li key={index} className="font-mono text-xs text-slate-600">
                    {line}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
