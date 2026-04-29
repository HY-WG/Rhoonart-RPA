import { createClient } from "@/lib/supabase/server";
import { getUser } from "@/lib/auth";
import { Youtube, TrendingUp, FileText, AlertCircle } from "lucide-react";
import Link from "next/link";

type ChannelInfo = {
  channel_name: string | null;
  channel_url: string | null;
  subscriber_count: number | null;
  monthly_views: number | null;
};

async function getCreatorProfile(): Promise<ChannelInfo> {
  const supabase = await createClient();
  const user = await getUser();
  if (!user) return { channel_name: null, channel_url: null, subscriber_count: null, monthly_views: null };

  const { data } = await supabase
    .from("profiles")
    .select("channel_name, channel_url, subscriber_count, monthly_views")
    .eq("user_id", user.id)
    .single();

  return data ?? { channel_name: null, channel_url: null, subscriber_count: null, monthly_views: null };
}

async function getPendingRequestsCount(): Promise<number> {
  const supabase = await createClient();
  const user = await getUser();
  if (!user) return 0;

  const { count } = await supabase
    .from("work_requests")
    .select("*", { count: "exact", head: true })
    .eq("creator_id", user.id)
    .eq("status", "pending");

  return count ?? 0;
}

function formatNumber(n: number | null): string {
  if (n === null) return "-";
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  return n.toLocaleString("ko-KR");
}

export default async function PortalPage() {
  const [profile, pendingCount] = await Promise.all([
    getCreatorProfile().catch(() => ({
      channel_name: null,
      channel_url: null,
      subscriber_count: null,
      monthly_views: null,
    })),
    getPendingRequestsCount().catch(() => 0),
  ]);

  return (
    <div className="p-8 max-w-3xl">
      {/* 환영 헤더 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">내 채널 현황</h1>
        <p className="text-slate-500 text-sm mt-1">
          루나트 크리에이터 포털에 오신 것을 환영합니다.
        </p>
      </div>

      {/* 채널 정보 카드 */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Youtube className="w-4 h-4 text-red-500" />
            내 채널
          </h2>
          {profile.channel_url && (
            <a
              href={profile.channel_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-indigo-500 hover:underline flex items-center gap-1"
            >
              채널 바로가기 →
            </a>
          )}
        </div>

        {profile.channel_name ? (
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-slate-400 mb-1">채널명</p>
              <p className="font-semibold text-slate-800">{profile.channel_name}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">구독자</p>
              <p className="font-semibold text-slate-800">
                {formatNumber(profile.subscriber_count)}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">이번 달 조회수</p>
              <p className="font-semibold text-slate-800">
                {formatNumber(profile.monthly_views)}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 rounded-lg px-4 py-3">
            <AlertCircle className="w-4 h-4 shrink-0" />
            채널 정보가 아직 등록되지 않았습니다. 관리자에게 문의해 주세요.
          </div>
        )}
      </div>

      {/* 빠른 메뉴 */}
      <div className="grid grid-cols-2 gap-4">
        <Link
          href="/portal/requests"
          className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow group"
        >
          <div className="flex items-start justify-between mb-3">
            <div className="p-2 bg-indigo-50 rounded-lg">
              <FileText className="w-5 h-5 text-indigo-500" />
            </div>
            {pendingCount > 0 && (
              <span className="text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                {pendingCount}건 처리 중
              </span>
            )}
          </div>
          <p className="font-semibold text-slate-800 text-sm">작품 사용 신청</p>
          <p className="text-xs text-slate-400 mt-1">
            사용 신청 현황을 확인합니다.
          </p>
        </Link>

        <Link
          href="/portal/performance"
          className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow group"
        >
          <div className="mb-3">
            <div className="p-2 bg-emerald-50 rounded-lg w-fit">
              <TrendingUp className="w-5 h-5 text-emerald-500" />
            </div>
          </div>
          <p className="font-semibold text-slate-800 text-sm">성과 확인</p>
          <p className="text-xs text-slate-400 mt-1">
            채널 성과 및 수익 현황을 확인합니다.
          </p>
        </Link>
      </div>
    </div>
  );
}
