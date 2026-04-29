import { cn, statusColor } from "@/lib/utils";
import type { RunStatus } from "@/lib/types";

const statusLabel: Record<RunStatus, string> = {
  queued:    "대기 중",
  running:   "실행 중",
  succeeded: "성공",
  failed:    "실패",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        statusColor[status] ?? "bg-gray-100 text-gray-600"
      )}
    >
      {statusLabel[status] ?? status}
    </span>
  );
}
