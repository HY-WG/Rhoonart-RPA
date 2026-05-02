"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const SECTIONS = [
  {
    id: "channel",
    label: "1. 채널 관리",
    items: [
      { href: "/admin/channels", label: "채널 관리" },
      { href: "/admin/lead-discovery", label: "리드 채널 발굴" },
      { href: "/admin/lead-email", label: "리드 채널 메일 발송" },
    ],
  },
  {
    id: "work",
    label: "2. 작품 관리",
    items: [
      { href: "/admin/new-work", label: "신규작품 등록" },
      { href: "/admin/naver-work", label: "네이버 작품 정보 추가" },
      { href: "/admin/work-application", label: "작품 사용 신청 진행상황" },
    ],
  },
  {
    id: "report",
    label: "3. 월별 보고",
    items: [
      { href: "/admin/naver-report", label: "네이버 월별 성과보고" },
    ],
  },
];

export default function AdminSidebar() {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    channel: true,
    work: true,
    report: true,
  });

  const toggle = (id: string) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col min-h-full">
      <nav className="flex-1 py-3">
        {SECTIONS.map((section) => {
          const isOpen = expanded[section.id];
          return (
            <div key={section.id} className="mb-1">
              <button
                onClick={() => toggle(section.id)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-gray-800 hover:bg-gray-50 transition-colors"
              >
                <span>{section.label}</span>
                {isOpen ? (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-400" />
                )}
              </button>

              {isOpen && (
                <div className="mb-1">
                  {section.items.map((item) => {
                    const active = pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`block px-6 py-2 text-sm transition-colors ${
                          active
                            ? "bg-teal-50 text-teal-600 font-medium"
                            : "text-gray-500 hover:bg-gray-50 hover:text-gray-800"
                        }`}
                      >
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
