import Link from "next/link";

const NAV = [
  { href: "/dashboard",               label: "홈",           icon: "🏠" },
  { href: "/dashboard/ops-admin",     label: "운영지원 어드민", icon: "⚙️" },
  { href: "/dashboard/homepage-auto", label: "홈페이지 자동화", icon: "🌐" },
  { href: "/dashboard/approvals",     label: "승인 대기",      icon: "✅" },
  { href: "/dashboard/channels",      label: "내 채널",        icon: "📺" },
  { href: "/dashboard/runs",          label: "실행 기록",       icon: "📋" },
  { href: "/dashboard/resources",     label: "환경 요약",       icon: "🔧" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      {/* 사이드바 */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        {/* 로고 */}
        <div className="px-5 py-5 border-b border-gray-100">
          <span className="font-bold text-base text-blue-600 tracking-tight">
            Rhoonart
          </span>
          <span className="block text-[10px] text-gray-400 mt-0.5">
            운영 대시보드
          </span>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 py-3 space-y-0.5 px-2">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-gray-600
                         hover:bg-gray-50 hover:text-gray-900 transition-colors"
            >
              <span className="text-base leading-none">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        {/* 하단 정보 */}
        <div className="p-4 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 leading-relaxed">
            Python API: localhost:8001
          </p>
          <div className="mt-2 inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-[10px] text-gray-500">연결됨</span>
          </div>
        </div>
      </aside>

      {/* 콘텐츠 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 상단 헤더 */}
        <header className="bg-white border-b border-gray-200 px-6 py-3.5 flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-gray-900">
              Rhoonart 운영 대시보드
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              자동화 도구 실행, 채널 관리, 성과 확인을 한 화면에서
            </p>
          </div>
        </header>

        {/* 메인 */}
        <main className="flex-1 px-6 py-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
