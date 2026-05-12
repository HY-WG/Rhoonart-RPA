"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Clock, Mail, Save } from "lucide-react";
import { fetchNaverReportSchedules, updateNaverReportSchedule } from "@/lib/api";
import { CACHE_SEMI_STATIC } from "@/lib/query-client";
import type { NaverReportSchedule, NaverReportScheduleUpdate } from "@/lib/types";

const DAYS = [
  { value: 1, label: "월" },
  { value: 2, label: "화" },
  { value: 3, label: "수" },
  { value: 4, label: "목" },
  { value: 5, label: "금" },
  { value: 6, label: "토" },
  { value: 7, label: "일" },
];

function timeValue(value: string) {
  return value ? value.slice(0, 5) : "11:00";
}

function toForm(schedule: NaverReportSchedule): NaverReportScheduleUpdate {
  return {
    enabled: schedule.enabled,
    days_of_week: [...new Set(schedule.days_of_week)].sort(),
    send_time: timeValue(schedule.send_time),
    timezone: schedule.timezone || "Asia/Seoul",
    recipient_emails: [...new Set(schedule.recipient_emails ?? [])],
    include_work_ids: [...new Set(schedule.include_work_ids ?? [])].sort((a, b) => a - b),
  };
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function daySummary(days: number[]) {
  return DAYS.filter((day) => days.includes(day.value)).map((day) => day.label).join(", ");
}

export default function NaverReportSchedulePage() {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<number, NaverReportScheduleUpdate>>({});
  const query = useQuery({
    queryKey: ["naver-report-schedules"],
    queryFn: fetchNaverReportSchedules,
    ...CACHE_SEMI_STATIC,
  });

  const mutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: NaverReportScheduleUpdate }) =>
      updateNaverReportSchedule(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["naver-report-schedules"] });
    },
  });

  const worksByHolder = useMemo(() => {
    const map = new Map<number, NonNullable<typeof query.data>["works"]>();
    for (const work of query.data?.works ?? []) {
      map.set(work.rights_holder_id, [...(map.get(work.rights_holder_id) ?? []), work]);
    }
    return map;
  }, [query.data?.works]);

  const scheduleDraft = (schedule: NaverReportSchedule) =>
    drafts[schedule.schedule_id] ?? toForm(schedule);

  const sortedSchedules = useMemo(() => {
    return [...(query.data?.schedules ?? [])].sort((a, b) => {
      const aEnabled = scheduleDraft(a).enabled ? 1 : 0;
      const bEnabled = scheduleDraft(b).enabled ? 1 : 0;
      if (aEnabled !== bEnabled) return bEnabled - aEnabled;
      return a.rights_holder_name.localeCompare(b.rights_holder_name, "ko");
    });
  }, [query.data?.schedules, drafts]);

  const setDraft = (
    schedule: NaverReportSchedule,
    updater: (value: NaverReportScheduleUpdate) => NaverReportScheduleUpdate
  ) => {
    setDrafts((prev) => ({
      ...prev,
      [schedule.schedule_id]: updater(prev[schedule.schedule_id] ?? toForm(schedule)),
    }));
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl">
        <div className="border-b border-slate-200 pb-5">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">
            성과보고
          </p>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">보고 스케줄</h1>
          <p className="mt-1 text-sm text-slate-500">
            권리사별 자동 발송 요일, 시간, 수신자, 포함 작품을 관리합니다.
          </p>
        </div>

        {query.isLoading && (
          <div className="mt-6 rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-400">
            스케줄 정보를 불러오는 중입니다.
          </div>
        )}

        {query.isError && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-600">
            오류: {(query.error as Error).message}
          </div>
        )}

        {query.data && (
          <div className="mt-5 space-y-5">
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-slate-900">권리사 현황</h2>
                <p className="text-xs text-slate-500">
                  활성 {sortedSchedules.filter((item) => scheduleDraft(item).enabled).length} / 전체 {sortedSchedules.length}
                </p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {sortedSchedules.map((schedule) => {
                  const draft = scheduleDraft(schedule);
                  return (
                    <span
                      key={schedule.schedule_id}
                      className={[
                        "rounded-full border px-3 py-1 text-xs font-medium",
                        draft.enabled
                          ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                          : "border-slate-200 bg-slate-50 text-slate-500",
                      ].join(" ")}
                    >
                      {schedule.rights_holder_name}
                    </span>
                  );
                })}
              </div>
            </section>

            <div className="grid gap-3">
              {sortedSchedules.map((schedule) => {
                const draft = scheduleDraft(schedule);
                const works = worksByHolder.get(schedule.rights_holder_id) ?? [];
                const saving = mutation.isPending;
                return (
                  <section
                    key={schedule.schedule_id}
                    className={[
                      "rounded-lg border p-4 shadow-sm transition-colors",
                      draft.enabled
                        ? "border-emerald-300 bg-emerald-50/70"
                        : "border-slate-200 bg-white opacity-85",
                    ].join(" ")}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-base font-semibold text-slate-900">
                            {schedule.rights_holder_name}
                          </h2>
                          <span
                            className={[
                              "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                              draft.enabled
                                ? "bg-emerald-600 text-white"
                                : "bg-slate-200 text-slate-600",
                            ].join(" ")}
                          >
                            {draft.enabled ? "활성" : "비활성"}
                          </span>
                          <span className="text-xs text-slate-500">
                            {daySummary(draft.days_of_week)} {draft.send_time}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                          <span className="inline-flex items-center gap-1">
                            <Mail className="h-3.5 w-3.5" />
                            {draft.recipient_emails.join(", ") || "수신자 없음"}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            마지막 발송: {formatDateTime(schedule.last_sent_at)}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700">
                          <input
                            type="checkbox"
                            checked={draft.enabled}
                            onChange={(event) =>
                              setDraft(schedule, (value) => ({
                                ...value,
                                enabled: event.target.checked,
                              }))
                            }
                            className="h-4 w-4 rounded border-slate-300"
                          />
                          활성
                        </label>
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() =>
                            mutation.mutate({ id: schedule.schedule_id, payload: draft })
                          }
                          className="inline-flex h-9 items-center gap-2 rounded-lg bg-slate-900 px-3 text-xs font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300"
                        >
                          <Save className="h-4 w-4" />
                          저장
                        </button>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 lg:grid-cols-[1.15fr_0.55fr_1.25fr]">
                      <div>
                        <p className="mb-1.5 text-xs font-semibold text-slate-700">요일</p>
                        <div className="flex flex-wrap gap-1.5">
                          {DAYS.map((day) => {
                            const active = draft.days_of_week.includes(day.value);
                            return (
                              <button
                                key={day.value}
                                type="button"
                                onClick={() =>
                                  setDraft(schedule, (value) => ({
                                    ...value,
                                    days_of_week: active
                                      ? value.days_of_week.filter((item) => item !== day.value)
                                      : [...value.days_of_week, day.value].sort(),
                                  }))
                                }
                                className={[
                                  "h-8 rounded-md border px-2.5 text-xs font-medium",
                                  active
                                    ? "border-blue-600 bg-blue-600 text-white"
                                    : "border-slate-300 bg-white text-slate-600",
                                ].join(" ")}
                              >
                                {day.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      <div>
                        <p className="mb-1.5 text-xs font-semibold text-slate-700">시간</p>
                        <input
                          type="time"
                          value={draft.send_time}
                          onChange={(event) =>
                            setDraft(schedule, (value) => ({
                              ...value,
                              send_time: event.target.value,
                            }))
                          }
                          className="h-9 w-full rounded-lg border border-slate-300 bg-white px-2 text-sm"
                        />
                      </div>

                      <div>
                        <p className="mb-1.5 text-xs font-semibold text-slate-700">수신자</p>
                        <input
                          value={draft.recipient_emails.join(", ")}
                          onChange={(event) =>
                            setDraft(schedule, (value) => ({
                              ...value,
                              recipient_emails: event.target.value
                                .split(",")
                                .map((item) => item.trim())
                                .filter(Boolean),
                            }))
                          }
                          placeholder="name@example.com, team@example.com"
                          className="h-9 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"
                        />
                      </div>
                    </div>

                    <div className="mt-3">
                      <p className="mb-1.5 text-xs font-semibold text-slate-700">포함 작품</p>
                      {works.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {works.map((work) => {
                            const checked = draft.include_work_ids.includes(work.work_id);
                            return (
                              <button
                                key={work.work_id}
                                type="button"
                                onClick={() =>
                                  setDraft(schedule, (value) => ({
                                    ...value,
                                    include_work_ids: checked
                                      ? value.include_work_ids.filter((id) => id !== work.work_id)
                                      : [...value.include_work_ids, work.work_id].sort((a, b) => a - b),
                                  }))
                                }
                                className={[
                                  "inline-flex min-h-8 items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs",
                                  checked
                                    ? "border-emerald-500 bg-white text-emerald-700"
                                    : "border-slate-300 bg-white text-slate-600",
                                ].join(" ")}
                              >
                                {checked && <Check className="h-3.5 w-3.5" />}
                                {work.work_title}
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-400">
                          활성화된 네이버 클립 보고 작품이 없습니다.
                        </p>
                      )}
                    </div>
                  </section>
                );
              })}
            </div>

            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">최근 발송 이력</h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs text-slate-500">
                    <tr>
                      <th className="py-2 pr-4">일시</th>
                      <th className="py-2 pr-4">상태</th>
                      <th className="py-2 pr-4">실행 모드</th>
                      <th className="py-2 pr-4">Run ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {query.data.logs.map((log) => (
                      <tr key={log.id}>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {formatDateTime(log.created_at)}
                        </td>
                        <td className="py-2.5 pr-4 text-slate-900">{log.status || "-"}</td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {log.execution_mode || "-"}
                        </td>
                        <td className="py-2.5 pr-4 font-mono text-xs text-slate-500">
                          {log.run_id || "-"}
                        </td>
                      </tr>
                    ))}
                    {query.data.logs.length === 0 && (
                      <tr>
                        <td className="py-7 text-center text-slate-400" colSpan={4}>
                          발송 이력이 없습니다.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
