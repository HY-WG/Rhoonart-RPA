"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { fetchChannelVideos, startRun } from "@/lib/api";
import { Button } from "./ui/button";
import type { ChannelVideo, IntegrationRun } from "@/lib/types";

const ACTION_CONFIGS = [
  { label: "\uc791\ud488\uc0ac\uc6a9\uc2e0\uccad \uc2b9\uc778", taskId: "A-2", variant: "primary" as const, buildPayload: (v: ChannelVideo) => ({ channel_name: v.channel_name, work_title: v.title, dry_run: true }) },
  { label: "\ucfe0\ud3f0 \uc694\uccad", taskId: "C-4", variant: "ghost" as const, buildPayload: (v: ChannelVideo) => ({ source: "dashboard", creator_name: v.channel_name, text: `${v.title} \ucfe0\ud3f0 \uc694\uccad\uc785\ub2c8\ub2e4.` }) },
  { label: "\uad8c\ub9ac \uc18c\uba85 \uc694\uccad", taskId: "D-2", variant: "soft" as const, buildPayload: (v: ChannelVideo) => ({ requester_channel_name: v.channel_name, requester_email: v.contact_email, auto_send_mails: false, items: [{ work_id: v.video_id, work_title: v.title, rights_holder_name: v.rights_holder_name, channel_folder_name: v.channel_name }] }) },
] as const;

function VideoCard({ video, onRunStarted }: { video: ChannelVideo; onRunStarted?: (run: IntegrationRun) => void }) {
  const qc = useQueryClient();
  const { mutate, isPending, variables } = useMutation({ mutationFn: ({ taskId, payload }: { taskId: string; payload: Record<string, unknown> }) => startRun(taskId, payload, "dry_run", false), onSuccess: (run) => { qc.invalidateQueries({ queryKey: ["runs"] }); onRunStarted?.(run); } });
  return <article className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden"><div className="flex gap-4 p-4"><div className="w-14 h-14 rounded-lg bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center text-2xl flex-shrink-0">{video.thumbnail_emoji || video.title.slice(0, 1)}</div><div className="flex-1 min-w-0"><div className="flex items-start justify-between gap-2"><div><h3 className="font-semibold text-sm text-gray-900">{video.title}</h3><p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{video.description}</p></div><span className="text-[10px] bg-green-100 text-green-700 rounded-full px-2 py-0.5 flex-shrink-0 font-medium">{video.availability_status}</span></div><div className="flex flex-wrap gap-1.5 mt-2"><span className="text-[11px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">{video.channel_name}</span><span className="text-[11px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">{video.rights_holder_name}</span><span className="text-[11px] bg-blue-50 text-blue-600 rounded-full px-2 py-0.5">{video.platform}</span></div></div></div><div className="flex gap-2 px-4 pb-4">{ACTION_CONFIGS.map((cfg) => <Button key={cfg.taskId} variant={cfg.variant} size="sm" loading={isPending && variables?.taskId === cfg.taskId} onClick={() => mutate({ taskId: cfg.taskId, payload: cfg.buildPayload(video) })}>{cfg.label}</Button>)}</div></article>;
}

export function ChannelPanel({ onRunStarted }: { onRunStarted?: (run: IntegrationRun) => void }) {
  const { data: videos = [], isLoading, refetch, isRefetching } = useQuery({ queryKey: ["channel-videos"], queryFn: fetchChannelVideos });
  return <section className="space-y-4"><div className="flex items-center justify-between"><p className="text-sm text-gray-500">{"\ub0b4 \ucc44\ub110\uc5d0\uc11c \uc774\uc6a9 \uac00\ub2a5\ud55c \uc601\uc0c1\uc744 \ud655\uc778\ud558\uace0 \uad00\ub828 \uc5c5\ubb34\ub97c \uc694\uccad\ud569\ub2c8\ub2e4."}</p><div className="flex items-center gap-2"><span className="text-xs text-gray-400">{"\uc601\uc0c1 "}{videos.length}{"\uac1c"}</span><Button variant="ghost" size="sm" loading={isRefetching} onClick={() => refetch()}><RefreshCw size={13} />{"\uc0c8\ub85c\uace0\uce68"}</Button></div></div>{isLoading ? <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-28 rounded-xl bg-gray-100 animate-pulse" />)}</div> : videos.length === 0 ? <div className="text-center py-16 text-gray-400 text-sm rounded-xl bg-gray-50 border border-gray-100">{"\uc774\uc6a9 \uac00\ub2a5\ud55c \uc601\uc0c1\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."}</div> : <div className="space-y-3">{videos.map((v) => <VideoCard key={v.video_id} video={v} onRunStarted={onRunStarted} />)}</div>}</section>;
}
