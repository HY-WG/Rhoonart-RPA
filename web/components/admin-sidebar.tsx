"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BarChart3, ChevronDown, ChevronRight, Film, PanelsTopLeft, ClipboardList } from "lucide-react";

const sections = [
  { id: "channels", label: "\ucc44\ub110 \uad00\ub9ac", icon: PanelsTopLeft, items: [{ href: "/admin/channels", label: "\ucc44\ub110 \uc870\ud68c" }, { href: "/admin/lead-discovery", label: "\ub9ac\ub4dc \ucc44\ub110 \ubc1c\uad74" }] },
  { id: "videos", label: "\uc601\uc0c1 \uad00\ub9ac", icon: Film, items: [{ href: "/admin/new-work", label: "\uc2e0\uaddc \uc601\uc0c1 \ub4f1\ub85d" }, { href: "/admin/videos", label: "\uc601\uc0c1\ubcc4 \ucc44\ub110 \ud604\ud669" }] },
  { id: "workapply", label: "\uc791\ud488 \uc0ac\uc6a9 \uc2e0\uccad", icon: ClipboardList, items: [{ href: "/admin/work-application", label: "\uc2e0\uccad \uc9c4\ud589 \ud604\ud669" }] },
  { id: "reports", label: "\uc131\uacfc\ubcf4\uace0", icon: BarChart3, items: [{ href: "/admin/reports/kakao", label: "\uce74\uce74\uc624 \uc6d4\ucd08 \uc810\uac80" }, { href: "/admin/reports/naver", label: "\ub124\uc774\ubc84 \uc6d4\ubcc4 \uc131\uacfc\ubcf4\uace0" }, { href: "/admin/reports/naver-clip", label: "\ub124\uc774\ubc84 \ud074\ub9bd \uc131\uacfc \ud655\uc778" }, { href: "/admin/reports/naver-supabase", label: "Naver Supabase \uc5c5\ub370\uc774\ud2b8" }] },
];

export default function AdminSidebar() {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ channels: true, videos: true, reports: true });
  return (
    <aside className="w-64 shrink-0 bg-white border-r border-slate-200 min-h-full">
      <nav className="py-4">
        {sections.map((section) => {
          const Icon = section.icon;
          const open = expanded[section.id];
          return (
            <div key={section.id} className="mb-2">
              <button onClick={() => setExpanded((prev) => ({ ...prev, [section.id]: !prev[section.id] }))} className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-50">
                <span className="flex items-center gap-2"><Icon className="w-4 h-4" />{section.label}</span>
                {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
              </button>
              {open && <div>{section.items.map((item) => <Link key={item.href} href={item.href} className={`block mx-2 rounded-md px-8 py-2 text-sm ${pathname === item.href ? "bg-blue-50 text-blue-700 font-medium" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"}`}>{item.label}</Link>)}</div>}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
