import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** RunStatus → Tailwind 색상 */
export const statusColor: Record<string, string> = {
  queued:    "bg-gray-100 text-gray-700",
  running:   "bg-amber-100 text-amber-700 animate-pulse",
  succeeded: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
};

/** 태스크 ID 카테고리 → 헤더 색상 */
export const categoryColor: Record<string, string> = {
  a: "from-blue-50 to-blue-100 border-blue-200",
  b: "from-purple-50 to-purple-100 border-purple-200",
  c: "from-emerald-50 to-emerald-100 border-emerald-200",
  d: "from-orange-50 to-orange-100 border-orange-200",
};

export const categoryBadge: Record<string, string> = {
  a: "bg-blue-600 text-white",
  b: "bg-purple-600 text-white",
  c: "bg-emerald-600 text-white",
  d: "bg-orange-600 text-white",
};

export function getCategoryFromId(taskId: string) {
  return taskId.split("-")[0].toLowerCase();
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}초 전`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.floor(h / 24)}일 전`;
}
