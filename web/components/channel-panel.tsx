"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { fetchChannelVideos, startRun } from "@/lib/api";
import { Button } from "./ui/button";
import type { ChannelVideo, IntegrationRun } from "@/lib/types";

interface ChannelPanelProps {
  onRunStarted?: (run: IntegrationRun) => void;
}

const ACTION_CONFIGS = [
  {
    actionType: "work-approval",
    label: "작품사용신청 승인",
    taskId: "A-2",
    variant: "primary" as const,
    buildPayload: (v: ChannelVideo) => ({
      channel_name: v.channel_name,
      work_title: v.title,
      dry_run: true,
    }),
  },
  {
    actionType: "coupon",
    label: "쿠폰 신청",
    taskId: "C-4",
    variant: "ghost" as const,
    buildPayload: (v: ChannelVideo) => ({
      source: "dashboard",
      creator_name: v.channel_name,
      text: `${v.title} 수익 100% 쿠폰 요청입니다.`,
    }),
  },
  {
    actionType: "relief",
    label: "저작권 소명 신청",
    taskId: "D-2",
    variant: "soft" as const,
    buildPayload: (v: ChannelVideo) => ({
      requester_channel_name: v.channel_name,
      requester_email: v.contact_email,
      auto_send_mails: false,
      items: [
        {
          work_id: v.video_id,
          work_title: v.title,
          rights_holder_name: v.rights_holder_name,
          channel_folder_name: v.channel_name,
        },
      ],
    }),
  },
] as const;

function VideoCard({
  video,
  onRunStarted,
}: {
  video: ChannelVideo;
  onRunStarted?: (run: IntegrationRun) => void;
}) {
  const qc = useQueryClient();
  const { mutate, isPending, variables } = useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string;
      payload: Record<string, unknown>;
    }) => startRun(taskId, payload, "dry_run", false),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      onRunStarted?.(run);
    },
  });

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="flex gap-4 p-4">
        <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center text-2xl flex-shrink-0">
          {video.thumbnail_emoji || video.title.slice(0, 1)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-semibold text-sm text-gray-900">{video.title}</h3>
              <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                {video.description}
              </p>
            </div>
            <span className="text-[10px] bg-green-100 text-green-700 rounded-full px-2 py-0.5 flex-shrink-0 font-medium">
              {video.availability_status}
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            <span className="text-[11px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">
              {video.channel_name}
            </span>
            <span className="text-[11px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">
              {video.rights_holder_name}
            </span>
            <span className="text-[11px] bg-blue-50 text-blue-600 rounded-full px-2 py-0.5">
              {video.platform}
            </span>
          </div>
        </div>
      </div>
      <div className="flex gap-2 px-4 pb-4">
        {ACTION_CONFIGS.map((cfg) => (
          <Button
            key={cfg.actionType}
            variant={cfg.variant}
            size="sm"
            loading={isPending && variables?.taskId === cfg.taskId}
            onClick={() =>
              mutate({ taskId: cfg.taskId, payload: cfg.buildPayload(video) })
            }
          >
            {cfg.label}
          </Button>
        ))}
      </div>
    </article>
  );
}

export function ChannelPanel({ onRunStarted }: ChannelPanelProps) {
  const { data: videos = [], isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["channel-videos"],
    queryFn: fetchChannelVideos,
  });

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          내 채널에서 이용 가능한 영상을 확인하고 관련 업무를 신청합니다.
        </p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">영상 {videos.length}개</span>
          <Button
            variant="ghost"
            size="sm"
            loading={isRefetching}
            onClick={() => refetch()}
          >
            <RefreshCw size={13} />
            새로고침
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : videos.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm rounded-xl bg-gray-50 border border-gray-100">
          이용 가능한 영상이 없습니다.
        </div>
      ) : (
        <div className="space-y-3">
          {videos.map((v) => (
            <VideoCard key={v.video_id} video={v} onRunStarted={onRunStarted} />
          ))}
        </div>
      )}
    </section>
  );
}
