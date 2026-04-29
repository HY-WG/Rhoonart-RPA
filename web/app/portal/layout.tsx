import Link from "next/link";
import { redirect } from "next/navigation";
import { getUserRole, getUser } from "@/lib/auth";
import { Home, FileText, BarChart2, LogOut } from "lucide-react";

const navItems = [
  { href: "/portal", label: "내 채널 현황", icon: Home },
  { href: "/portal/requests", label: "작품 사용 신청", icon: FileText },
  { href: "/portal/performance", label: "성과 확인", icon: BarChart2 },
];

export default async function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const role = await getUserRole();

  if (role !== "creator") {
    redirect("/login");
  }

  const user = await getUser();

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* 사이드바 */}
      <aside className="w-60 shrink-0 bg-white border-r border-slate-100 flex flex-col shadow-sm">
        {/* 로고 */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center font-bold text-sm text-white">
              R
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-800 leading-tight">
                Rhoonart
              </p>
              <p className="text-xs text-slate-400">크리에이터 포털</p>
            </div>
          </div>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-600 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          ))}
        </nav>

        {/* 유저 정보 + 로그아웃 */}
        <div className="px-4 py-4 border-t border-slate-100">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-xs font-bold shrink-0">
              {user?.email?.[0]?.toUpperCase() ?? "C"}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-slate-700 truncate">
                {user?.email ?? "크리에이터"}
              </p>
              <span className="text-xs text-indigo-400">creator</span>
            </div>
          </div>
          <form action="/auth/signout" method="POST">
            <button
              type="submit"
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-400 hover:bg-slate-50 hover:text-slate-600 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              로그아웃
            </button>
          </form>
        </div>
      </aside>

      {/* 본문 */}
      <main className="flex-1 min-w-0 overflow-auto">{children}</main>
    </div>
  );
}
