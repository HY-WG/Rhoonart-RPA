"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, CheckCircle2, Clock } from "lucide-react";
import {
  fetchAdminOverview,
  fetchOpsA3Report,
  fetchOpsB2Report,
  fetchOpsLeadSummary,
} from "@/lib/api";
import type { OpsA3Report, OpsB2Report, OpsLeadSummary } from "@/lib/types";

function StatusBadge({ status }: { status: "completed" | "pending" }) {
  if (status === "completed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        보고 완료
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
      <Clock className="h-3 w-3" />
      보고 대기중
    </span>
  );
}

function B2ReportCard({ data }: { data: OpsB2Report }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-slate-950">네이버 클립 &amp; 유튜브 통합 성과보고</h3>
        <Link href="/admin/reports/naver-clip">
          <ArrowRight className="h-4 w-4 text-slate-400" />
        </Link>
      </div>
      <p className="mt-1 text-xs text-slate-400">활성 권리사 {data.active_count}개</p>
      <ul className="mt-4 space-y-2.5">
        {data.rights_holders.map((rh) => (
          <li key={rh.name} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <span className="block text-sm font-medium text-slate-800">{rh.name}</span>
              <span className="block text-xs text-slate-400">
                {rh.schedule_days.join(", ")} {rh.schedule_time}
              </span>
            </div>
            <StatusBadge status={rh.report_status} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function A3ReportCard({ data }: { data: OpsA3Report }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-slate-950">네이버 클립 채널 인입</h3>
        <Link href="/admin/naver-work">
          <ArrowRight className="h-4 w-4 text-slate-400" />
        </Link>
      </div>
      <ul className="mt-4 space-y-3">
        <li className="flex items-center justify-between gap-3">
          <div>
            <span className="block text-xs text-slate-400">당월 보고일</span>
            <span className="block text-sm font-medium text-slate-800">{data.current_month.label}</span>
          </div>
          <StatusBadge status={data.current_month.status} />
        </li>
        <li className="flex items-center justify-between gap-3">
          <div>
            <span className="block text-xs text-slate-400">차월 보고일</span>
            <span className="block text-sm font-medium text-slate-800">{data.next_month.label}</span>
          </div>
          <StatusBadge status={data.next_month.status} />
        </li>
      </ul>
    </div>
  );
}

function LeadSummaryCard({ data }: { data: OpsLeadSummary }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-slate-950">리드 발굴 요약</h3>
        <Link href="/admin/videos">
          <ArrowRight className="h-4 w-4 text-slate-400" />
        </Link>
      </div>
      <p className="mt-4 text-sm text-slate-500">
        리드 발굴 필요 영상
        <span className="ml-2 text-2xl font-bold text-slate-950">{data.videos_needing_leads}</span>
        <span className="ml-1 text-sm text-slate-500">개</span>
      </p>
      <p className="mt-1 text-xs text-slate-400">이용 채널 수 5개 이하 영상 기준</p>
    </div>
  );
}

function OpsCardSkeleton() {
  return <div className="h-40 animate-pulse rounded-lg border border-slate-100 bg-slate-50" />;
}

export default function AdminPage() {
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: fetchAdminOverview });
  const b2 = useQuery({ queryKey: ["ops-b2-report"], queryFn: fetchOpsB2Report });
  const a3 = useQuery({ queryKey: ["ops-a3-report"], queryFn: fetchOpsA3Report });
  const lead = useQuery({ queryKey: ["ops-lead-summary"], queryFn: fetchOpsLeadSummary });

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-950">어드민</h1>
        <p className="mt-1 text-sm text-slate-500">작품, 채널, 파트너 협업 현황을 관리합니다.</p>
      </div>

      {/* 미결 사항 */}
      <section className="mb-10">
        <div className="mb-3 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-blue-700" />
          <h2 className="text-lg font-semibold text-slate-900">미결 사항</h2>
        </div>
        {overview.isLoading && (
          <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
            현황을 불러오는 중입니다.
          </div>
        )}
        {overview.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center text-sm text-red-700">
            {(overview.error as Error).message}
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-3">
          {overview.data?.pending.map((item) => (
            <Link
              key={item.id}
              href={
                item.id === "rights-relief"
                  ? "/admin/work-application"
                  : item.id === "naver-report"
                  ? "/admin/reports/naver"
                  : "/admin/videos"
              }
              className="rounded-lg border border-slate-200 bg-white p-5 hover:border-blue-200 hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <h3 className="font-semibold text-slate-950">{item.title}</h3>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </div>
              <p className="mt-4 text-sm text-slate-500">
                {item.metric_label} :{" "}
                <span className="text-2xl font-bold text-slate-950">{item.count}</span>
              </p>
            </Link>
          ))}
        </div>
      </section>

      {/* 운영 현황 */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-teal-600" />
          <h2 className="text-lg font-semibold text-slate-900">운영 현황</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {b2.isLoading ? <OpsCardSkeleton /> : b2.data ? <B2ReportCard data={b2.data} /> : null}
          {a3.isLoading ? <OpsCardSkeleton /> : a3.data ? <A3ReportCard data={a3.data} /> : null}
          {lead.isLoading ? <OpsCardSkeleton /> : lead.data ? <LeadSummaryCard data={lead.data} /> : null}
        </div>
      </section>
    </div>
  );
}
