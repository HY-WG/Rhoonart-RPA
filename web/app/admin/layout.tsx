import Link from "next/link";
import { redirect } from "next/navigation";
import { getUserRole, getUser } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import {
  LayoutDashboard,
  Users,
  CheckSquare,
  Settings,
  LogOut,
  ExternalLink,
} from "lucide-react";

const navItems = [
  { href: "/admin", label: "홈", icon: LayoutDashboard, exact: true },
  { href: "/admin/channels", label: "채널 승인", icon: CheckSquare },
  { href: "/admin/creators", label: "크리에이터 목록", icon: Users },
  { href: "/admin/settings", label: "설정", icon: Settings },
];

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const role = await getUserRole();

  if (role !== "admin") {
    redirect("/login");
  }

  const user = await getUser();

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* 사이드바 */}
      <aside className="w-60 shrink-0 bg-slate-900 text-white flex flex-col">
        {/* 로고 */}
        <div className="px-5 py-5 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center font-bold text-sm">
              R
            </div>
            <div>
              <p className="text-sm font-semibold leading-tight">Rhoonart</p>
              <p className="text-xs text-slate-400">Admin 패널</p>
            </div>
          </div>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ href, label, icon: Icon, exact }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          ))}

          {/* RPA 대시보드 외부 링크 */}
          <div className="pt-3 mt-3 border-t border-slate-700">
            <Link
              href="/dashboard"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
            >
              <ExternalLink className="w-4 h-4 shrink-0" />
              RPA 대시보드
            </Link>
          </div>
        </nav>

        {/* 유저 정보 + 로그아웃 */}
        <div className="px-4 py-4 border-t border-slate-700">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold shrink-0">
              {user?.email?.[0]?.toUpperCase() ?? "A"}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium truncate">
                {user?.email ?? "관리자"}
              </p>
              <span className="text-xs text-indigo-300">admin</span>
            </div>
          </div>
          <LogoutButton />
        </div>
      </aside>

      {/* 본문 */}
      <main className="flex-1 min-w-0 overflow-auto">{children}</main>
    </div>
  );
}

function LogoutButton() {
  return (
    <form action="/auth/signout" method="POST">
      <button
        type="submit"
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
      >
        <LogOut className="w-3.5 h-3.5" />
        로그아웃
      </button>
    </form>
  );
}
