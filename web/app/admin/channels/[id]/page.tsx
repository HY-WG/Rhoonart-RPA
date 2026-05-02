"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use } from "react";
import { createClient } from "@/lib/supabase/client";
import { ArrowLeft, ExternalLink, Check, X } from "lucide-react";

/* ─── 타입 ─── */
type ChannelApproval = {
  id: string;
  channel_name: string;
  channel_url: string | null;
  creator_email: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  processed_at?: string | null;
};

/* ─── 상태 표시 ─── */
const STATUS_LABEL: Record<string, string> = {
  approved: "승인",
  pending: "대기중",
  rejected: "거부",
};
const statusStyle = (s: string) => {
  if (s === "approved") return "bg-teal-50 text-teal-600 border-teal-200";
  if (s === "pending") return "bg-yellow-50 text-yellow-600 border-yellow-200";
  return "bg-red-50 text-red-500 border-red-200";
};

/* ─── 날짜 포맷 ─── */
const fmt = (s?: string | null) =>
  s ? new Date(s).toLocaleDateString("ko-KR").replace(/\.$/, "") : "-";

/* ─── 아바타 ─── */
const avatarSeed = (name: string) =>
  `https://i.pravatar.cc/80?u=${encodeURIComponent(name)}`;

/* ─── Supabase 훅 ─── */
function useChannel(id: string) {
  return useQuery({
    queryKey: ["channel-approval", id],
    queryFn: async () => {
      const supabase = createClient();
      const { data, error } = await supabase
        .from("channel_approvals")
        .select("*")
        .eq("id", id)
        .single();
      if (error) throw error;
      return data as ChannelApproval;
    },
  });
}

function useUpdateStatus(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (status: "approved" | "rejected") => {
      const supabase = createClient();
      const { error } = await supabase
        .from("channel_approvals")
        .update({ status, processed_at: new Date().toISOString() })
        .eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["channel-approval", id] });
      qc.invalidateQueries({ queryKey: ["channel-approvals"] });
    },
  });
}

/* ─── 확인 모달 ─── */
function ConfirmModal({
  action,
  channelName,
  onConfirm,
  onCancel,
  loading,
}: {
  action: "approved" | "rejected";
  channelName: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const isApprove = action === "approved";
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-2">
          채널 {isApprove ? "승인" : "거부"} 확인
        </h3>
        <p className="text-sm text-gray-500 mb-6">
          <span className="font-medium text-gray-800">{channelName}</span> 채널을{" "}
          {isApprove ? "승인" : "거부"}하시겠습니까?
          {!isApprove && (
            <span className="block mt-1 text-red-500">
              거부된 채널은 크리에이터에게 안내 이메일이 발송됩니다.
            </span>
          )}
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 py-2.5 border border-gray-300 text-sm text-gray-600 rounded-xl hover:bg-gray-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 py-2.5 text-white text-sm font-semibold rounded-xl disabled:opacity-50 transition-colors flex items-center justify-center gap-2 ${
              isApprove
                ? "bg-teal-500 hover:bg-teal-600"
                : "bg-red-500 hover:bg-red-600"
            }`}
          >
            {loading ? (
              "처리 중..."
            ) : (
              <>
                {isApprove ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <X className="w-4 h-4" />
                )}
                {isApprove ? "승인" : "거부"}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── 메인 페이지 ─── */
export default function ChannelDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data: channel, isLoading, isError } = useChannel(id);
  const mutation = useUpdateStatus(id);
  const [confirmAction, setConfirmAction] = useState<"approved" | "rejected" | null>(null);

  const handleConfirm = () => {
    if (!confirmAction) return;
    mutation.mutate(confirmAction, {
      onSuccess: () => setConfirmAction(null),
    });
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center h-64 text-gray-400 text-sm">
        불러오는 중...
      </div>
    );
  }

  if (isError || !channel) {
    return (
      <div className="p-8">
        <p className="text-red-500 text-sm">채널 정보를 불러올 수 없습니다.</p>
        <button
          onClick={() => router.back()}
          className="mt-4 text-sm text-teal-600 hover:underline"
        >
          뒤로 가기
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="p-8 max-w-3xl">
        {/* 뒤로가기 */}
        <button
          onClick={() => router.push("/admin/channels")}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          채널 목록으로
        </button>

        {/* 채널 헤더 카드 */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={avatarSeed(channel.channel_name)}
                alt={channel.channel_name}
                className="w-16 h-16 rounded-full object-cover shrink-0"
              />
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  {channel.channel_name}
                </h1>
                {channel.channel_url && (
                  <a
                    href={channel.channel_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-sm text-teal-600 hover:text-teal-700 mt-0.5"
                  >
                    {channel.channel_url}
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </div>
            <span
              className={`px-3 py-1 text-sm rounded-full font-medium border ${statusStyle(channel.status)}`}
            >
              {STATUS_LABEL[channel.status] ?? channel.status}
            </span>
          </div>
        </div>

        {/* 상세 정보 카드 */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-5">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">채널 정보</h2>
          </div>
          <div className="divide-y divide-gray-50">
            <InfoRow label="크리에이터 이메일" value={channel.creator_email} />
            <InfoRow label="신청 상태" value={STATUS_LABEL[channel.status] ?? channel.status} />
            <InfoRow label="등록일" value={fmt(channel.requested_at)} />
            <InfoRow label="처리일" value={fmt(channel.processed_at)} />
            <InfoRow label="채널 ID" value={channel.id} mono />
          </div>
        </div>

        {/* 승인/거부 액션 (pending 상태일 때만) */}
        {channel.status === "pending" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">승인 관리</h2>
            {mutation.isError && (
              <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg mb-4">
                오류: {(mutation.error as Error)?.message}
              </p>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmAction("rejected")}
                disabled={mutation.isPending}
                className="flex-1 py-2.5 border border-red-300 text-sm text-red-600 font-medium rounded-xl hover:bg-red-50 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                <X className="w-4 h-4" />
                거부
              </button>
              <button
                onClick={() => setConfirmAction("approved")}
                disabled={mutation.isPending}
                className="flex-1 py-2.5 bg-teal-500 text-white text-sm font-semibold rounded-xl hover:bg-teal-600 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                <Check className="w-4 h-4" />
                승인
              </button>
            </div>
          </div>
        )}

        {/* 이미 처리된 경우: 상태 변경 버튼 */}
        {channel.status !== "pending" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">상태 변경</h2>
            <div className="flex gap-3">
              {channel.status === "approved" ? (
                <button
                  onClick={() => setConfirmAction("rejected")}
                  disabled={mutation.isPending}
                  className="px-5 py-2.5 border border-red-300 text-sm text-red-600 font-medium rounded-xl hover:bg-red-50 disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  <X className="w-4 h-4" />
                  승인 취소 (거부로 변경)
                </button>
              ) : (
                <button
                  onClick={() => setConfirmAction("approved")}
                  disabled={mutation.isPending}
                  className="px-5 py-2.5 bg-teal-500 text-white text-sm font-semibold rounded-xl hover:bg-teal-600 disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  승인으로 변경
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 확인 모달 */}
      {confirmAction && (
        <ConfirmModal
          action={confirmAction}
          channelName={channel.channel_name}
          onConfirm={handleConfirm}
          onCancel={() => setConfirmAction(null)}
          loading={mutation.isPending}
        />
      )}
    </>
  );
}

/* ─── 정보 행 컴포넌트 ─── */
function InfoRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center px-6 py-3.5">
      <span className="w-40 shrink-0 text-sm text-gray-500">{label}</span>
      <span className={`text-sm text-gray-800 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </span>
    </div>
  );
}
