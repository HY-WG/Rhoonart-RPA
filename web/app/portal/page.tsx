"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, FileText, ShieldCheck, Video } from "lucide-react";
import { applyCreator, fetchChannelVideos, fetchMyChannels, requestRelief, requestVideoUsage } from "@/lib/api";
import type { Platform } from "@/lib/types";

const platformLabel: Record<Platform, string> = { youtube: "YouTube", kakao: "\uce74\uce74\uc624", naver: "\ub124\uc774\ubc84" };

function StateMessage({ title, detail }: { title: string; detail?: string }) {
  return <div className="rounded-lg border border-slate-200 bg-white px-5 py-8 text-center"><p className="font-medium text-slate-900">{title}</p>{detail && <p className="mt-1 text-sm text-slate-500">{detail}</p>}</div>;
}

export default function PortalPage() {
  const channels = useQuery({ queryKey: ["my-channels"], queryFn: fetchMyChannels });
  const videos = useQuery({ queryKey: ["my-videos"], queryFn: fetchChannelVideos });
  const creatorMutation = useMutation({ mutationFn: ({ channelId, platform }: { channelId: string; platform: "kakao" | "naver" }) => applyCreator(channelId, platform) });
  const usageMutation = useMutation({ mutationFn: requestVideoUsage });
  const reliefMutation = useMutation({ mutationFn: requestRelief });

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4"><div><h1 className="text-2xl font-bold text-slate-950">{"\ub0b4 \ucc44\ub110"}</h1><p className="mt-1 text-sm text-slate-500">{"\ucc44\ub110 \uc2e0\uccad\uacfc \uc601\uc0c1\ubcc4 \uad8c\ub9ac \uc694\uccad\uc744 \ud55c \ud654\uba74\uc5d0\uc11c \ucc98\ub9ac\ud569\ub2c8\ub2e4."}</p></div>{(creatorMutation.data || usageMutation.data || reliefMutation.data) && <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700"><CheckCircle2 className="h-4 w-4" />{"\ucd5c\uadfc \uc694\uccad\uc774 \uc811\uc218\ub418\uc5c8\uc2b5\ub2c8\ub2e4."}</div>}</div>
      <section className="mb-8">
        <div className="mb-3 flex items-center gap-2"><FileText className="h-5 w-5 text-blue-700" /><h2 className="text-lg font-semibold text-slate-900">{"\ub0b4 \ucc44\ub110 \ub9ac\uc2a4\ud2b8"}</h2></div>
        {channels.isLoading && <StateMessage title={"\ucc44\ub110 \uc815\ubcf4\ub97c \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."} />}
        {channels.isError && <StateMessage title={"\ucc44\ub110 \uc815\ubcf4\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4."} detail={(channels.error as Error).message} />}
        {channels.data?.items.length === 0 && <StateMessage title={"\ub4f1\ub85d\ub41c \ucc44\ub110\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."} />}
        {channels.data && channels.data.items.length > 0 && <div className="overflow-hidden rounded-lg border border-slate-200 bg-white"><table className="w-full min-w-[760px] text-sm"><thead className="bg-slate-50 text-left text-slate-500"><tr><th className="px-5 py-3 font-medium">{"\ub0b4 \ucc44\ub110"}</th><th className="px-5 py-3 font-medium">{"\ub4f1\ub85d\uc77c\uc790"}</th><th className="px-5 py-3 font-medium">{"\ud50c\ub7ab\ud3fc"}</th><th className="px-5 py-3 font-medium">{"\uc0c1\ud0dc"}</th><th className="px-5 py-3 font-medium">{"\uc2e0\uccad"}</th></tr></thead><tbody className="divide-y divide-slate-100">{channels.data.items.map((channel) => <tr key={channel.channel_id} className="hover:bg-slate-50"><td className="px-5 py-4 font-medium text-slate-900">{channel.name}</td><td className="px-5 py-4 text-slate-600">{channel.registered_at}</td><td className="px-5 py-4 text-slate-600">{platformLabel[channel.platform]}</td><td className="px-5 py-4"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{channel.status}</span></td><td className="px-5 py-4"><div className="flex flex-wrap gap-2"><button onClick={() => creatorMutation.mutate({ channelId: channel.channel_id, platform: "kakao" })} className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">{"\uce74\uce74\uc624 \ud06c\ub9ac\uc5d0\uc774\ud130 \uc2e0\uccad\ud558\uae30"}</button><button onClick={() => creatorMutation.mutate({ channelId: channel.channel_id, platform: "naver" })} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">{"\ub124\uc774\ubc84 \ud06c\ub9ac\uc5d0\uc774\ud130 \uc2e0\uccad\ud558\uae30"}</button></div></td></tr>)}</tbody></table></div>}
      </section>
      <section>
        <div className="mb-3 flex items-center gap-2"><Video className="h-5 w-5 text-blue-700" /><h2 className="text-lg font-semibold text-slate-900">{"\ub0b4 \uc601\uc0c1"}</h2></div>
        {videos.isLoading && <StateMessage title={"\uc601\uc0c1 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."} />}
        {videos.isError && <StateMessage title={"\uc601\uc0c1 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4."} detail={(videos.error as Error).message} />}
        <div className="grid gap-4 lg:grid-cols-3">{videos.data?.map((video) => <article key={video.video_id} className="overflow-hidden rounded-lg border border-slate-200 bg-white"><img src={video.thumbnail_url} alt="" className="h-36 w-full object-cover" /><div className="p-5"><div className="mb-2 flex items-center justify-between gap-2"><h3 className="font-semibold text-slate-950">{video.title}</h3><span className="text-xs text-slate-500">{platformLabel[video.platform]}</span></div><p className="line-clamp-2 text-sm text-slate-500">{video.description}</p><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-400">{"\uad8c\ub9ac\uc0ac"}</dt><dd className="font-medium text-slate-800">{video.rights_holder_name}</dd></div><div><dt className="text-slate-400">{"\ub4f1\ub85d\uc77c"}</dt><dd className="font-medium text-slate-800">{video.registered_at}</dd></div></dl><div className="mt-5 flex gap-2"><button onClick={() => usageMutation.mutate(video.video_id)} className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"><ExternalLink className="h-4 w-4" />{"\uc601\uc0c1\uad8c\ud55c \uc2e0\uccad"}</button><button onClick={() => reliefMutation.mutate(video.video_id)} className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"><ShieldCheck className="h-4 w-4" />{"\uad8c\ub9ac\uc18c\uba85\uc694\uccad"}</button></div></div></article>)}</div>
      </section>
    </div>
  );
}
