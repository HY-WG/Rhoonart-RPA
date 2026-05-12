"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  ChevronDown,
  ChevronRight,
  Film,
  Handshake,
  PanelsTopLeft,
  ClipboardList,
  Users,
} from "lucide-react";
import { fetchNaverReportSchedules } from "@/lib/api";
import { CACHE_SEMI_STATIC } from "@/lib/query-client";

const sections = [
  {
    id: "channels",
    label: "채널 관리",
    icon: PanelsTopLeft,
    items: [
      { href: "/admin/channels", label: "채널 조회" },
      { href: "/admin/lead-discovery", label: "리드 채널 관리" },
    ],
  },
  {
    id: "videos",
    label: "영상 관리",
    icon: Film,
    items: [
      { href: "/admin/new-work", label: "신규 영상 등록" },
      { href: "/admin/videos", label: "영상별 채널 현황" },
    ],
  },
  {
    id: "workapply",
    label: "작품 사용 신청",
    icon: ClipboardList,
    items: [{ href: "/admin/work-application", label: "신청 진행 현황" }],
  },
  {
    id: "rights-admin",
    label: "권리사 관리",
    icon: Handshake,
    items: [
      { href: "/admin/copyright-claims", label: "저작권 소명 요청 리스트" },
      { href: "/admin/official-documents", label: "공문 작성" },
    ],
  },
  {
    id: "partner",
    label: "권리사 관리",
    icon: Handshake,
    items: [
      { href: "/partner/relief", label: "저작권 소명 요청 리스트" },
    ],
  },
  {
    id: "naver",
    label: "네이버 클립 관리",
    icon: BarChart3,
    items: [
      { href: "/admin/reports/naver-clip", label: "네이버 클립 성과 확인" },
      { href: "/admin/reports/naver-works", label: "보고 작품 관리" },
      { href: "/admin/reports/naver-schedule", label: "보고 스케줄" },
      { href: "/admin/naver-monthly", label: "네이버 클립 채널 인입" },
    ],
  },
  {
    id: "kakao",
    label: "카카오 크리에이터",
    icon: Users,
    items: [
      { href: "/admin/kakao-creators", label: "Supabase kakao_creators LIST" },
    ],
  },
];

export default function AdminSidebar() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const isPartnerDomain = pathname.startsWith("/partner");
  const visibleSections = isPartnerDomain
    ? sections.filter((section) => section.id === "partner")
    : sections.filter((section) => section.id !== "partner");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    channels: true,
    videos: true,
    workapply: true,
    "rights-admin": true,
    partner: true,
    naver: true,
    kakao: true,
  });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: ["naver-report-schedules"],
        queryFn: fetchNaverReportSchedules,
        ...CACHE_SEMI_STATIC,
      });
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [queryClient]);

  return (
    <aside className="w-64 shrink-0 bg-white border-r border-slate-200 min-h-full">
      <nav className="py-4">
        {visibleSections.map((section) => {
          const Icon = section.icon;
          const open = expanded[section.id];
          return (
            <div key={section.id} className="mb-1">
              <button
                onClick={() =>
                  setExpanded((prev) => ({ ...prev, [section.id]: !prev[section.id] }))
                }
                className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-50"
              >
                <span className="flex items-center gap-2">
                  <Icon className="w-4 h-4" />
                  {section.label}
                </span>
                {open ? (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                )}
              </button>
              {open && (
                <div>
                  {section.items.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onMouseEnter={() => {
                        if (item.href === "/admin/reports/naver-schedule") {
                          queryClient.prefetchQuery({
                            queryKey: ["naver-report-schedules"],
                            queryFn: fetchNaverReportSchedules,
                            ...CACHE_SEMI_STATIC,
                          });
                        }
                      }}
                      className={`block mx-2 rounded-md px-8 py-2 text-sm transition-colors ${
                        pathname === item.href
                          ? "bg-blue-50 text-blue-700 font-medium"
                          : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
