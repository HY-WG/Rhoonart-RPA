"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { X } from "lucide-react";

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

/* ─── 필터 탭 ─── */
const TABS = [
  { key: "all",      label: "전체" },
  { key: "approved", label: "승인" },
  { key: "pending",  label: "대기중" },
  { key: "rejected", label: "거부" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

/* ─── 상태 표시 매핑 ─── */
const STATUS_LABEL: Record<string, string> = {
  approved: "승인",
  pending:  "대기중",
  rejected: "거부",
};
const statusStyle = (s: string) => {
  if (s === "approved") return "bg-teal-50 text-teal-600";
  if (s === "pending")  return "bg-yellow-50 text-yellow-600";
  return "bg-red-50 text-red-500";
};

/* ─── 아바타 해시 ─── */
const avatarSeed = (name: string) =>
  `https://i.pravatar.cc/40?u=${encodeURIComponent(name)}`;

/* ─── 날짜 포맷 ─── */
const fmt = (s?: string | null) =>
  s ? new Date(s).toLocaleDateString("ko-KR").replace(/\.$/, "") : "-";

/* ─── Supabase 훅 ─── */
function useChannels(tab: TabKey) {
  return useQuery({
    queryKey: ["channel-approvals", tab],
    queryFn: async () => {
      const supabase = createClient();
      let q = supabase
        .from("channel_approvals")
        .select("*")
        .order("requested_at", { ascending: false });
      if (tab !== "all") q = q.eq("status", tab);
      const { data, error } = await q;
      if (error) throw error;
      return (data ?? []) as ChannelApproval[];
    },
    refetchInterval: 30_000,
  });
}

function useAddChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      channel_name: string;
      channel_url: string;
      creator_email: string;
    }) => {
      const supabase = createClient();
      const { error } = await supabase
        .from("channel_approvals")
        .insert({ ...payload, status: "pending" });
      if (error) throw error;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["channel-approvals"] }),
  });
}

/* ─── 채널 추가 모달 ─── */
function AddChannelModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({
    channel_name: "",
    channel_url: "",
    creator_email: "",
  });
  const mutation = useAddChannel();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form, {
      onSuccess: () => onClose(),
    });
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-gray-900">채널 추가</h2>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">채널명 *</label>
            <input
              required
              value={form.channel_name}
              onChange={(e) => setForm((f) => ({ ...f, channel_name: e.target.value }))}
              placeholder="채널 이름"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">채널 URL</label>
            <input
              value={form.channel_url}
              onChange={(e) => setForm((f) => ({ ...f, channel_url: e.target.value }))}
              placeholder="https://youtube.com/@channel"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">크리에이터 이메일 *</label>
            <input
              required
              type="email"
              value={form.creator_email}
              onChange={(e) => setForm((f) => ({ ...f, creator_email: e.target.value }))}
              placeholder="creator@example.com"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            />
          </div>

          {mutation.isError && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">
              오류: {(mutation.error as Error)?.message}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 border border-gray-300 text-sm text-gray-600 rounded-xl hover:bg-gray-50"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 py-2.5 bg-teal-500 text-white text-sm font-semibold rounded-xl hover:bg-teal-600 disabled:opacity-50"
            >
              {mutation.isPending ? "추가 중..." : "추가"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── 메인 페이지 ─── */
export default function ChannelsPage() {
  const router = useRouter();
  const [tab, setTab] = useState<TabKey>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const { data: channels = [], isLoading } = useChannels(tab);

  return (
    <>
      <div className="p-8">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">채널 관리</h1>
            <span className="px-3 py-1 bg-gray-100 text-gray-500 text-sm rounded-full font-medium">
              전체 {channels.length}개
            </span>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="px-5 py-2.5 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 transition-colors"
          >
            채널 추가
          </button>
        </div>

        {/* 필터 탭 */}
        <div className="flex gap-1 mb-5 bg-gray-100 p-1 rounded-xl w-fit">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-colors ${
                tab === key
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 테이블 */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
              불러오는 중...
            </div>
          ) : channels.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
              해당하는 채널이 없습니다.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">채널</th>
                  <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">상태</th>
                  <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">크리에이터</th>
                  <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">등록일</th>
                  <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">승인일</th>
                  <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">관리</th>
                </tr>
              </thead>
              <tbody>
                {channels.map((ch) => (
                  <tr
                    key={ch.id}
                    onClick={() => router.push(`/admin/channels/${ch.id}`)}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={avatarSeed(ch.channel_name)}
                          alt={ch.channel_name}
                          className="w-9 h-9 rounded-full object-cover shrink-0"
                        />
                        <div>
                          <p className="text-sm font-medium text-gray-800">{ch.channel_name}</p>
                          {ch.channel_url && (
                            <a
                              href={ch.channel_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-xs text-gray-400 hover:text-teal-500 truncate max-w-[160px] block"
                            >
                              {ch.channel_url}
                            </a>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`px-3 py-1 text-sm rounded-full font-medium ${statusStyle(ch.status)}`}
                      >
                        {STATUS_LABEL[ch.status] ?? ch.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{ch.creator_email}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{fmt(ch.requested_at)}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{fmt(ch.processed_at)}</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/admin/channels/${ch.id}`);
                        }}
                        className="text-sm text-teal-600 hover:text-teal-700 font-medium"
                      >
                        수정
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* 채널 추가 모달 */}
      {modalOpen && <AddChannelModal onClose={() => setModalOpen(false)} />}
    </>
  );
}
