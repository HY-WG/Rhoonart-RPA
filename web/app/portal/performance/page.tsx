import { createClient } from "@/lib/supabase/server";
import { getUser } from "@/lib/auth";
import { BarChart2, TrendingUp, Eye, ExternalLink } from "lucide-react";

type PerformanceStat = {
  month: string; // "2026-04"
  monthly_views: number;
  monthly_shorts_views: number;
  subscriber_count: number;
};

async function getPerformanceStats(): Promise<PerformanceStat[]> {
  const supabase = await createClient();
  const user = await getUser();
  if (!user) return [];

  const { data, error } = await supabase
    .from("channel_stats")
    .select("month, monthly_views, monthly_shorts_views, subscriber_count")
    .eq("creator_id", user.id)
    .order("month", { ascending: false })
    .limit(6);

  if (error) return [];
  return (data ?? []) as PerformanceStat[];
}

async function getLookerDashboardUrl(): Promise<string | null> {
  const supabase = await createClient();
  const user = await getUser();
  if (!user) return null;

  const { data } = await supabase
    .from("profiles")
    .select("looker_url")
    .eq("user_id", user.id)
    .single();

  return data?.looker_url ?? null;
}

function formatViews(n: number): string {
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}억`;
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  return n.toLocaleString("ko-KR");
}

export default async function PerformancePage() {
  const [stats, lookerUrl] = await Promise.all([
    getPerformanceStats().catch(() => [] as PerformanceStat[]),
    getLookerDashboardUrl().catch(() => null),
  ]);

  const latest = stats[0];

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-emerald-500" />
            성과 확인
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            내 채널의 최근 6개월 성과 데이터입니다.
          </p>
        </div>
        {lookerUrl && (
          <a
            href={lookerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-4 py-2 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            상세 대시보드
          </a>
        )}
      </div>

      {/* 이번 달 요약 */}
      {latest && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            {
              label: "이번 달 조회수",
              value: formatViews(latest.monthly_views),
              icon: Eye,
              color: "text-indigo-600",
              bg: "bg-indigo-50",
            },
            {
              label: "Shorts 조회수",
              value: formatViews(latest.monthly_shorts_views),
              icon: TrendingUp,
              color: "text-emerald-600",
              bg: "bg-emerald-50",
            },
            {
              label: "구독자 수",
              value: formatViews(latest.subscriber_count),
              icon: BarChart2,
              color: "text-amber-600",
              bg: "bg-amber-50",
            },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <div
              key={label}
              className="bg-white rounded-xl border border-slate-200 p-5"
            >
              <div className={`${bg} p-2 rounded-lg w-fit mb-3`}>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <p className="text-xs text-slate-400 mb-1">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* 월별 추이 테이블 */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">월별 추이</h2>
        </div>
        {stats.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-slate-400 gap-2">
            <BarChart2 className="w-8 h-8 opacity-30" />
            <p className="text-sm">아직 성과 데이터가 없습니다.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="text-left px-5 py-3 text-slate-500 font-medium">월</th>
                <th className="text-right px-5 py-3 text-slate-500 font-medium">전체 조회수</th>
                <th className="text-right px-5 py-3 text-slate-500 font-medium">Shorts 조회수</th>
                <th className="text-right px-5 py-3 text-slate-500 font-medium">구독자</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {stats.map((s, i) => (
                <tr
                  key={s.month}
                  className={`hover:bg-slate-50 transition-colors ${i === 0 ? "font-medium" : ""}`}
                >
                  <td className="px-5 py-3 text-slate-700">{s.month}</td>
                  <td className="px-5 py-3 text-right text-slate-600">
                    {formatViews(s.monthly_views)}
                  </td>
                  <td className="px-5 py-3 text-right text-slate-600">
                    {formatViews(s.monthly_shorts_views)}
                  </td>
                  <td className="px-5 py-3 text-right text-slate-600">
                    {formatViews(s.subscriber_count)}
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
