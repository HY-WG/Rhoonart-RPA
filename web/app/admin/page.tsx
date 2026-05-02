"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

type StatusItem = {
  id: string;
  label: string;
  count: number;
  badgeColor: string;
  subItems?: { label: string; count: number }[];
};

const PENDING_ITEMS: StatusItem[] = [
  {
    id: "onboarding",
    label: "온보딩 미결",
    count: 2,
    badgeColor: "bg-red-100 text-red-500",
    subItems: [
      { label: "카카오", count: 1 },
      { label: "네이버", count: 0 },
      { label: "레이블리", count: 1 },
    ],
  },
  {
    id: "copyright",
    label: "저작권 소명 요청",
    count: 0,
    badgeColor: "bg-gray-100 text-gray-500",
  },
  {
    id: "coupon",
    label: "쿠폰 지급 미결",
    count: 1,
    badgeColor: "bg-yellow-100 text-yellow-600",
  },
  {
    id: "brand",
    label: "브랜드 채널 개설 요청",
    count: 5,
    badgeColor: "bg-orange-100 text-orange-500",
  },
];

const STATUS_ITEMS: StatusItem[] = [
  {
    id: "meeting",
    label: "현재 진행중인 미팅",
    count: 3,
    badgeColor: "bg-teal-100 text-teal-600",
  },
];

function AccordionCard({ item }: { item: StatusItem }) {
  const [open, setOpen] = useState(item.id === "onboarding");
  const hasChildren = item.subItems && item.subItems.length > 0;

  return (
    <div className="border border-gray-200 rounded-xl bg-white">
      <button
        onClick={() => hasChildren && setOpen((p) => !p)}
        className={`w-full flex items-center justify-between px-5 py-4 ${hasChildren ? "cursor-pointer" : "cursor-default"}`}
      >
        <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
          {hasChildren && (
            open
              ? <ChevronDown className="w-4 h-4 text-gray-400" />
              : <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
          <span className={hasChildren ? "" : "ml-6"}>{item.label}</span>
        </div>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${item.badgeColor}`}>
          현황: {item.count}
        </span>
      </button>

      {hasChildren && open && (
        <div className="border-t border-gray-100 px-5 py-3 space-y-2">
          {item.subItems!.map((sub) => (
            <div key={sub.label} className="flex items-center justify-between text-sm">
              <span className="text-teal-500 hover:underline cursor-pointer">{sub.label}</span>
              <span className="text-gray-600">{sub.count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">대시보드</h1>

      {/* 미결상황 */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-800 mb-3">미결상황</h2>
        <div className="space-y-3">
          {PENDING_ITEMS.map((item) => (
            <AccordionCard key={item.id} item={item} />
          ))}
        </div>
      </section>

      {/* 현황 */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3">현황</h2>
        <div className="space-y-3">
          {STATUS_ITEMS.map((item) => (
            <AccordionCard key={item.id} item={item} />
          ))}
        </div>
      </section>
    </div>
  );
}
