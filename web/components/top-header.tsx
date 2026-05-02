"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard } from "lucide-react";

const tabs = [
  { href: "/portal", label: "\ub0b4 \ucc44\ub110" },
  { href: "/admin", label: "\uc5b4\ub4dc\ubbfc" },
];

export default function TopHeader() {
  const pathname = usePathname();
  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-10">
        <Link href="/portal" className="flex items-center gap-2.5">
          <span className="w-8 h-8 bg-slate-900 rounded-lg flex items-center justify-center text-white"><LayoutDashboard className="w-4 h-4" /></span>
          <span className="font-semibold text-slate-950 text-base">Rhoonart RPA</span>
        </Link>
        <nav className="flex items-center gap-7">
          {tabs.map((tab) => {
            const active = pathname.startsWith(tab.href);
            return <Link key={tab.href} href={tab.href} className={`text-sm pb-0.5 transition-colors ${active ? "text-blue-700 font-semibold border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-900"}`}>{tab.label}</Link>;
          })}
        </nav>
      </div>
    </header>
  );
}
