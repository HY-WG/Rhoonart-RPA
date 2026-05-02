"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function TopHeader() {
  const pathname = usePathname();

  const tabs = [
    { href: "/", label: "홈" },
    { href: "/portal", label: "내채널" },
    { href: "/admin", label: "어드민" },
  ];

  const activeTab = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 shrink-0">
      <div className="flex items-center gap-10">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            ㄹ
          </div>
          <span className="font-semibold text-gray-900 text-base">레이블리</span>
        </Link>

        <nav className="flex items-center gap-8">
          {tabs.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={`text-sm pb-0.5 transition-colors ${
                activeTab(tab.href)
                  ? "text-teal-600 font-medium border-b-2 border-teal-500"
                  : "text-gray-500 hover:text-gray-800"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
