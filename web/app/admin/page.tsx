import { createClient } from "@/lib/supabase/server";
import Link from "next/link";
import { CheckSquare, Users, ArrowRight, Clock } from "lucide-react";

async function getAdminStats(supabase: Awaited<ReturnType<typeof createClient>>) {
  const [{ count: pendingCount }, { count: creatorCount }] = await Promise.all([
    supabase
      .from("channel_approvals")
      .select("*", { count: "exact", head: true })
      .eq("status", "pending"),
    supabase
      .from("user_roles")
      .select("*", { count: "exact", head: true })
      .eq("role", "creator"),
  ]);

  return {
    pendingApprovals: pendingCount ?? 0,
    totalCreators: creatorCount ?? 0,
  };
}

export default async function AdminPage() {
  const supabase = await createClient();
  const stats = await getAdminStats(supabase).catch(() => ({
    pendingApprovals: 0,
    totalCreators: 0,
  }));

  const cards = [
    {
      title: "채널 승인 대기",
      value: stats.pendingApprovals,
      unit: "건",
      icon: CheckSquare,
      href: "/admin/channels",
      color: "text-amber-600",
      bg: "bg-amber-50",
      urgent: stats.pendingApprovals > 0,
    },
    {
      title: "등록 크리에이터",
      value: stats.totalCreators,
      unit: "명",
      icon: Users,
      href: "/admin/creators",
      color: "text-indigo-600",
      bg: "bg-indigo-50",
      urgent: false,
    },
  ];

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">관리자 홈</h1>
        <p className="text-slate-500 text-sm mt-1">Rhoonart 운영 현황을 확인합니다.</p>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        {cards.map(({ title, value, unit, icon: Icon, href, color, bg, urgent }) => (
          <Link
            key={href}
            href={href}
            className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-md transition-shadow group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-slate-500 mb-1">{title}</p>
                <p className={`text-3xl font-bold ${color}`}>
                  {value}
                  <span className="text-base font-normal ml-1 text-slate-400">{unit}</span>
                </p>
              </div>
              <div className={`${bg} p-3 rounded-xl relative`}>
                <Icon className={`w-5 h-5 ${color}`} />
                {urgent && (
                  <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-500 rounded-full" />
                )}
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-slate-400 group-hover:text-indigo-500 transition-colors">
              <span>자세히 보기</span>
              <ArrowRight className="w-3 h-3" />
            </div>
          </Link>
        ))}
      </div>

      {/* 빠른 링크 */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4" />
          빠른 작업
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <Link
            href="/admin/channels"
            className="flex items-center gap-2 px-4 py-3 bg-amber-50 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-100 transition-colors"
          >
            <CheckSquare className="w-4 h-4" />
            채널 승인 처리
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-4 py-3 bg-slate-50 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-100 transition-colors"
          >
            <ArrowRight className="w-4 h-4" />
            RPA 대시보드 이동
          </Link>
        </div>
      </div>
    </div>
  );
}
