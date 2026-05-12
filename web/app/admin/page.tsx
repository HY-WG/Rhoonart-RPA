"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  ClipboardList,
  FileWarning,
  Landmark,
  Users,
} from "lucide-react";
import { fetchAdminOverview } from "@/lib/api";
import type { PendingItem } from "@/lib/types";

const ICONS = {
  "work-application": ClipboardList,
  "rights-relief": FileWarning,
  "naver-youtube-report": BarChart3,
  "naver-revenue": Landmark,
  "lead-summary": Users,
};

const CARD_BASE =
  "rounded-lg border border-slate-200 bg-white p-5 hover:border-blue-200 hover:shadow-sm";

function CardHeader({ item, Icon }: { item: PendingItem; Icon: React.ElementType }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
          <Icon className="h-5 w-5" />
        </span>
        <h3 className="font-semibold text-slate-950">{item.title}</h3>
      </div>
      <ArrowRight className="h-4 w-4 text-slate-400" />
    </div>
  );
}

function B2ReportCard({ item, Icon }: { item: PendingItem; Icon: React.ElementType }) {
  const rhs = item.rights_holders ?? [];
  return (
    <Link key={item.id} href={item.href ?? "/admin/reports/naver-clip"} className={CARD_BASE}>
      <CardHeader item={item} Icon={Icon} />
      {rhs.length === 0 ? (
        <p className="mt-5 text-sm text-slate-400">등록된 권리사 일정이 없습니다.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rhs.map((rh) => (
            <li key={rh.name} className="flex items-center justify-between gap-2">
              <div className="flex items-baseline gap-2 min-w-0">
                <span className="truncate text-sm font-medium text-slate-800">{rh.name}</span>
                {rh.schedule && (
                  <span className="whitespace-nowrap text-xs text-slate-400">{rh.schedule}</span>
                )}
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                  rh.status === "보고 완료"
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                {rh.status}
              </span>
            </li>
          ))}
        </ul>
      )}
      {item.status && (
        <p className="mt-3 text-xs font-medium text-slate-400">{item.status}</p>
      )}
    </Link>
  );
}

function A3ReportCard({ item, Icon }: { item: PendingItem; Icon: React.ElementType }) {
  const dates = item.report_dates;
  return (
    <Link key={item.id} href={item.href ?? "/admin/naver-monthly"} className={CARD_BASE}>
      <CardHeader item={item} Icon={Icon} />
      <div className="mt-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-slate-400">당월 보고일</p>
            <p className="mt-0.5 text-sm font-semibold text-slate-900">
              {dates?.current ?? "-"}
            </p>
          </div>
          <span
            className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
              dates?.current_sent
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700"
            }`}
          >
            {dates?.current_sent ? "보고 완료" : "보고 대기중"}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-slate-400">차월 보고일</p>
            <p className="mt-0.5 text-sm font-medium text-slate-500">
              {dates?.next ?? "-"}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
            보고 대기중
          </span>
        </div>
      </div>
    </Link>
  );
}

function GenericCard({ item, Icon }: { item: PendingItem; Icon: React.ElementType }) {
  return (
    <Link key={item.id} href={item.href ?? "/admin/videos"} className={CARD_BASE}>
      <CardHeader item={item} Icon={Icon} />
      <p className="mt-5 text-sm text-slate-500">
        {item.metric_label} :{" "}
        <span className="text-2xl font-bold text-slate-950">
          {item.count.toLocaleString()}
        </span>
      </p>
      {item.status && (
        <p className="mt-2 text-xs font-medium text-slate-400">{item.status}</p>
      )}
    </Link>
  );
}

export default function AdminPage() {
  const overview = useQuery({
    queryKey: ["admin-overview"],
    queryFn: fetchAdminOverview,
    refetchOnWindowFocus: true,
    refetchInterval: 15000,
  });

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-950">어드민</h1>
        <p className="mt-1 text-sm text-slate-500">
          작품, 권리사 소명, 성과 보고, 수익 보고, 리드 발굴 현황을 관리합니다.
        </p>
      </div>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-blue-700" />
          <h2 className="text-lg font-semibold text-slate-900">운영 카드</h2>
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
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {overview.data?.pending.map((item) => {
            const Icon = ICONS[item.id as keyof typeof ICONS] ?? AlertCircle;
            if (item.id === "naver-youtube-report") {
              return <B2ReportCard key={item.id} item={item} Icon={Icon} />;
            }
            if (item.id === "naver-revenue") {
              return <A3ReportCard key={item.id} item={item} Icon={Icon} />;
            }
            return <GenericCard key={item.id} item={item} Icon={Icon} />;
          })}
        </div>
      </section>
    </div>
  );
}
