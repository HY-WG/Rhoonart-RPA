"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchAdminVideos } from "@/lib/api";

export default function AdminVideosPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["admin-videos"], queryFn: fetchAdminVideos });

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-slate-900">영상별 채널 현황</h1>
      <p className="mt-1 text-sm text-slate-500">
        이용 중인 채널 수가 5개 이하인 영상은 리드채널 관리 화면에서 발굴을 진행합니다.
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-slate-400">영상을 불러오는 중입니다.</div>
        )}
        {query.isError && (
          <div className="p-8 text-center text-sm text-red-500">
            {(query.error as Error).message}
          </div>
        )}
        {query.data && (
          <div className="divide-y divide-slate-100">
            {query.data.items.map((video) => {
              const canDiscover = video.active_channel_count <= 5;
              return (
                <div
                  key={video.video_id}
                  className={[
                    "grid grid-cols-[88px_1fr_auto_auto] items-center gap-4 p-5",
                    canDiscover ? "bg-amber-50/40" : "",
                  ].join(" ")}
                >
                  <img
                    src={video.thumbnail_url}
                    alt=""
                    className="h-14 w-20 rounded-md bg-slate-100 object-cover"
                  />
                  <div>
                    <h2 className="font-semibold text-slate-900">{video.title}</h2>
                    <p className="mt-1 text-sm text-slate-500">등록일 {video.registered_at}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-400">이용 중인 채널 수</p>
                    <p className="font-semibold text-slate-900">{video.active_channel_count}개</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {canDiscover ? (
                      <button
                        type="button"
                        onClick={() => router.push("/admin/lead-discovery")}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-teal-500 px-3 py-2 text-sm font-medium text-white hover:bg-teal-600"
                      >
                        리드 발굴 진행
                      </button>
                    ) : (
                      <span className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-400">
                        채널 충분
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
