"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createClient } from "@/lib/supabase/client";
import { CheckSquare, X, Check, ExternalLink, RefreshCw } from "lucide-react";

type ChannelApproval = {
  id: string;
  channel_id: string;
  channel_name: string;
  channel_url: string;
  creator_email: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
};

function useChannelApprovals(status: string) {
  return useQuery({
    queryKey: ["channel-approvals", status],
    queryFn: async () => {
      const supabase = createClient();
      const query = supabase
        .from("channel_approvals")
        .select("*")
        .order("requested_at", { ascending: false });

      if (status !== "all") query.eq("status", status);
      const { data, error } = await query;
      if (error) throw error;
      return (data ?? []) as ChannelApproval[];
    },
    refetchInterval: 15000,
  });
}

function useApprovalMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      ids,
      action,
    }: {
      ids: string[];
      action: "approved" | "rejected";
    }) => {
      const supabase = createClient();
      const { error } = await supabase
        .from("channel_approvals")
        .update({ status: action, processed_at: new Date().toISOString() })
        .in("id", ids);
      if (error) throw error;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["channel-approvals"] });
    },
  });
}

export default function ChannelsPage() {
  const [tab, setTab] = useState<"pending" | "approved" | "rejected" | "all">("pending");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data: items = [], isLoading, refetch } = useChannelApprovals(tab);
  const mutation = useApprovalMutation();

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected(
      selected.size === items.length
        ? new Set()
        : new Set(items.map((i) => i.id))
    );
  };

  const handleBulkAction = (action: "approved" | "rejected") => {
    if (selected.size === 0) return;
    mutation.mutate(
      { ids: Array.from(selected), action },
      { onSuccess: () => setSelected(new Set()) }
    );
  };

  const tabs = [
    { key: "pending", label: "대기 중" },
    { key: "approved", label: "승인됨" },
    { key: "rejected", label: "거절됨" },
    { key: "all", label: "전체" },
  ] as const;

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <CheckSquare className="w-6 h-6 text-amber-500" />
            채널 승인 관리
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            크리에이터 채널 초대 요청을 일괄 처리합니다.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-500 hover:text-slate-700 border border-slate-200 rounded-lg"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          새로고침
        </button>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 mb-4 bg-slate-100 p-1 rounded-lg w-fit">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => {
              setTab(key);
              setSelected(new Set());
            }}
            className={`px-4 py-1.5 text-sm rounded-md font-medium transition-colors ${
              tab === key
                ? "bg-white text-slate-800 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Bulk Action 버튼 */}
      {selected.size > 0 && (
        <div className="mb-4 flex items-center gap-3 px-4 py-3 bg-indigo-50 border border-indigo-200 rounded-xl">
          <span className="text-sm font-medium text-indigo-700">
            {selected.size}개 선택됨
          </span>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={() => handleBulkAction("approved")}
              disabled={mutation.isPending}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-500 text-white text-sm font-medium rounded-lg hover:bg-emerald-600 disabled:opacity-50"
            >
              <Check className="w-3.5 h-3.5" />
              일괄 승인
            </button>
            <button
              onClick={() => handleBulkAction("rejected")}
              disabled={mutation.isPending}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50"
            >
              <X className="w-3.5 h-3.5" />
              일괄 거절
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700 border border-slate-200 rounded-lg"
            >
              취소
            </button>
          </div>
        </div>
      )}

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
            불러오는 중...
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-400 gap-2">
            <CheckSquare className="w-8 h-8 opacity-30" />
            <p className="text-sm">처리할 항목이 없습니다.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selected.size === items.length && items.length > 0}
                    onChange={toggleAll}
                    className="rounded"
                  />
                </th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">채널명</th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">크리에이터</th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">요청일</th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">상태</th>
                <th className="w-24 px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`hover:bg-slate-50 transition-colors ${
                    selected.has(item.id) ? "bg-indigo-50" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(item.id)}
                      onChange={() => toggleSelect(item.id)}
                      className="rounded"
                    />
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-800">
                    <div className="flex items-center gap-2">
                      {item.channel_name}
                      {item.channel_url && (
                        <a
                          href={item.channel_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-400 hover:text-indigo-500"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{item.creator_email}</td>
                  <td className="px-4 py-3 text-slate-400">
                    {new Date(item.requested_at).toLocaleDateString("ko-KR")}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3">
                    {item.status === "pending" && (
                      <div className="flex gap-1">
                        <button
                          onClick={() =>
                            mutation.mutate({ ids: [item.id], action: "approved" })
                          }
                          className="p-1.5 text-emerald-500 hover:bg-emerald-50 rounded"
                          title="승인"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() =>
                            mutation.mutate({ ids: [item.id], action: "rejected" })
                          }
                          className="p-1.5 text-red-400 hover:bg-red-50 rounded"
                          title="거절"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: ChannelApproval["status"] }) {
  const map = {
    pending: "bg-amber-50 text-amber-600",
    approved: "bg-emerald-50 text-emerald-600",
    rejected: "bg-red-50 text-red-500",
  };
  const label = { pending: "대기 중", approved: "승인됨", rejected: "거절됨" };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status]}`}>
      {label[status]}
    </span>
  );
}
