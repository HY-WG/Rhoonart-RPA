"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ExternalLink,
  FileText,
  ShieldCheck,
  Video,
  X,
} from "lucide-react";
import {
  createNaverRevenueSettlement,
  fetchChannelVideos,
  fetchMyChannels,
  requestRelief,
  requestVideoUsage,
} from "@/lib/api";
import type { MyChannel, Platform } from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001/dashboard";
const rpaBase = apiBase.replace(/\/dashboard$/, "").replace(/\/$/, "");
const platformLabel: Record<Platform, string> = {
  youtube: "YouTube",
  kakao: "카카오",
  naver: "네이버",
};

type SettlementForm = {
  name: string;
  channel_name: string;
  revenue_month: string;
  monthly_revenue: string;
  screenshot: File | null;
};

type CompletionNotice = {
  type: "usage" | "relief";
  title: string;
  videoTitle?: string;
};

const EMPTY_SETTLEMENT_FORM: SettlementForm = {
  name: "",
  channel_name: "",
  revenue_month: new Date().toISOString().slice(0, 7),
  monthly_revenue: "",
  screenshot: null,
};

function StateMessage({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-5 py-8 text-center">
      <p className="font-medium text-slate-900">{title}</p>
      {detail && <p className="mt-1 text-sm text-slate-500">{detail}</p>}
    </div>
  );
}

function creatorFormUrl(path: "/a3/apply" | "/d3/apply", channel: MyChannel) {
  const params = new URLSearchParams({
    channel_id: channel.channel_id,
    channel_name: channel.name,
    platform: channel.platform,
  });
  return `${rpaBase}${path}?${params.toString()}`;
}

function FormLink({
  href,
  children,
  className,
}: {
  href: string;
  children: React.ReactNode;
  className: string;
}) {
  return (
    <a href={href} className={className}>
      {children}
    </a>
  );
}

function SettlementModal({
  channel,
  onClose,
}: {
  channel: MyChannel;
  onClose: () => void;
}) {
  const [form, setForm] = useState<SettlementForm>({
    ...EMPTY_SETTLEMENT_FORM,
    channel_name: channel.name,
  });

  const mutation = useMutation({
    mutationFn: () =>
      createNaverRevenueSettlement({
        name: form.name,
        channel_name: form.channel_name,
        revenue_month: form.revenue_month,
        monthly_revenue: form.monthly_revenue,
        screenshot: form.screenshot,
      }),
  });

  const setField =
    (key: keyof SettlementForm) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [key]: event.target.value }));
    };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-950">네이버 수익금 정산</h2>
            <p className="mt-1 text-sm text-slate-500">
              입력한 정보와 캡쳐 이미지는 Supabase에 저장됩니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100"
            aria-label="닫기"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-5 grid gap-3">
          <label className="text-sm font-medium text-slate-700">
            이름
            <input required value={form.name} onChange={setField("name")} className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            채널명
            <input required value={form.channel_name} onChange={setField("channel_name")} className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            정산 월
            <input required type="month" value={form.revenue_month} onChange={setField("revenue_month")} className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            당월 수익금
            <input required inputMode="numeric" value={form.monthly_revenue} onChange={setField("monthly_revenue")} placeholder="예: 125000" className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            월 수익금 화면 캡쳐 이미지
            <input
              required
              type="file"
              accept="image/*"
              onChange={(event) => setForm((prev) => ({ ...prev, screenshot: event.target.files?.[0] ?? null }))}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>

        {mutation.isError && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
            {(mutation.error as Error).message}
          </p>
        )}
        {mutation.isSuccess && (
          <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            정산 정보가 Supabase에 저장되었습니다.
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700">
            닫기
          </button>
          <button disabled={mutation.isPending} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
            {mutation.isPending ? "저장 중" : "저장"}
          </button>
        </div>
      </form>
    </div>
  );
}

function CompletionPage({
  notice,
  onBack,
}: {
  notice: CompletionNotice;
  onBack: () => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-full bg-emerald-100 p-2 text-emerald-700">
          <CheckCircle2 className="h-6 w-6" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500">{notice.videoTitle}</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">{notice.title}</h2>
        </div>
      </div>

      {notice.type === "usage" ? (
        <div className="space-y-4 text-sm leading-6 text-slate-700">
          <p className="text-lg font-semibold text-slate-950">신청해 주셔서 감사합니다!</p>
          <p>
            신청 내역은 관리자 승인 단계로 전달되었습니다. 승인 완료 후 입력하신 이메일로
            영상 링크가 발송될 예정입니다.
          </p>
          <p>
            <strong>스팸 메일함 확인:</strong> 메일이 스팸으로 분류되었는지 확인 부탁드립니다.
          </p>
          <p>
            <strong>진행 안내:</strong> 신청 현황에서 승인 대기, 승인, 반려 상태를 확인하실 수 있습니다.
          </p>
          <p>
            <strong>문의하기:</strong> 재시도 후에도 문제가 지속된다면 관리자에게 문의해 주시면
            신속히 도와드리겠습니다.
          </p>
        </div>
      ) : (
        <div className="space-y-4 text-sm leading-6 text-slate-700">
          <p>
            본 요청은 관련 절차에 따라 검토되며, 완료까지는 최대 7일 정도의 기간이 소요될 예정입니다.
            검토가 완료되는 대로 앱 알림을 통해 개별 안내를 드릴 예정이오니 참고 부탁드립니다.
          </p>
          <p>
            기한 내 처리가 지연되거나 확인이 필요하신 경우에는 관리자에게 문의해 주시면 성심껏 답변해 드리겠습니다.
          </p>
        </div>
      )}

      {notice.type === "usage" && (
        <Link
          href="/portal/requests"
          className="mt-8 mr-3 inline-flex rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          신청 진행 현황 보기
        </Link>
      )}

      <button
        type="button"
        onClick={onBack}
        className="mt-8 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        영상 목록으로 돌아가기
      </button>
    </div>
  );
}

export default function PortalPage() {
  const [settlementChannel, setSettlementChannel] = useState<MyChannel | null>(null);
  const [completionNotice, setCompletionNotice] = useState<CompletionNotice | null>(null);
  const channels = useQuery({ queryKey: ["my-channels"], queryFn: fetchMyChannels });
  const videos = useQuery({ queryKey: ["my-videos"], queryFn: fetchChannelVideos });
  const usageMutation = useMutation({
    mutationFn: requestVideoUsage,
    onSuccess: (_result, video) => {
      setCompletionNotice({
        type: "usage",
        title: "영상권한 신청이 접수되었습니다.",
        videoTitle: video.title,
      });
    },
  });
  const reliefMutation = useMutation({
    mutationFn: requestRelief,
    onSuccess: (_result, video) => {
      setCompletionNotice({
        type: "relief",
        title: "권리소명 요청이 접수되었습니다.",
        videoTitle: video.title,
      });
    },
  });

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      {settlementChannel && (
        <SettlementModal channel={settlementChannel} onClose={() => setSettlementChannel(null)} />
      )}

      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">내 채널</h1>
          <p className="mt-1 text-sm text-slate-500">
            채널 신청과 영상별 관리 요청을 한 화면에서 처리합니다.
          </p>
        </div>
        {(usageMutation.isPending || reliefMutation.isPending) && (
          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            요청을 접수하는 중입니다.
          </div>
        )}
      </div>

      <section className="mb-8">
        <div className="mb-3 flex items-center gap-2">
          <FileText className="h-5 w-5 text-blue-700" />
          <h2 className="text-lg font-semibold text-slate-900">내 채널 리스트</h2>
        </div>
        {channels.isLoading && <StateMessage title="채널 정보를 불러오는 중입니다." />}
        {channels.isError && (
          <StateMessage title="채널 정보를 불러오지 못했습니다." detail={(channels.error as Error).message} />
        )}
        {channels.data?.items.length === 0 && <StateMessage title="등록된 채널이 없습니다." />}
        {channels.data && channels.data.items.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">내 채널</th>
                  <th className="px-5 py-3 font-medium">등록일자</th>
                  <th className="px-5 py-3 font-medium">플랫폼</th>
                  <th className="px-5 py-3 font-medium">상태</th>
                  <th className="px-5 py-3 font-medium">신청</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {channels.data.items.map((channel) => (
                  <tr key={channel.channel_id} className="hover:bg-slate-50">
                    <td className="px-5 py-4 font-medium text-slate-900">{channel.name}</td>
                    <td className="px-5 py-4 text-slate-600">{channel.registered_at}</td>
                    <td className="px-5 py-4 text-slate-600">{platformLabel[channel.platform]}</td>
                    <td className="px-5 py-4">
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                        {channel.status}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-2">
                        <FormLink
                          href={creatorFormUrl("/d3/apply", channel)}
                          className="inline-flex items-center rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          카카오 크리에이터 신청하기
                        </FormLink>
                        <FormLink
                          href={creatorFormUrl("/a3/apply", channel)}
                          className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                        >
                          네이버 클립 크리에이터 프로그램 등록
                        </FormLink>
                        {channel.platform === "naver" && (
                          <button
                            onClick={() => setSettlementChannel(channel)}
                            className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                          >
                            네이버 수익금 정산
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <Video className="h-5 w-5 text-blue-700" />
          <h2 className="text-lg font-semibold text-slate-900">내 영상</h2>
          <Link
            href="/portal/requests"
            className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            신청 진행 현황
          </Link>
        </div>
        {completionNotice && (
          <CompletionPage notice={completionNotice} onBack={() => setCompletionNotice(null)} />
        )}
        {!completionNotice && (
          <>
        {videos.isLoading && <StateMessage title="영상 목록을 불러오는 중입니다." />}
        {videos.isError && (
          <StateMessage title="영상 목록을 불러오지 못했습니다." detail={(videos.error as Error).message} />
        )}
        <div className="grid gap-4 lg:grid-cols-3">
          {videos.data?.map((video) => (
            <article key={video.video_id} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <img src={video.thumbnail_url} alt="" className="h-36 w-full object-cover" />
              <div className="p-5">
                <div className="mb-1 flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-slate-950">{video.title}</h3>
                  <span className="shrink-0 text-xs text-slate-500">{platformLabel[video.platform]}</span>
                </div>
                {video.rights_holder_name && (
                  <span className="mb-3 inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 ring-1 ring-blue-200">
                    권리사 · {video.rights_holder_name}
                  </span>
                )}
                <p className="line-clamp-2 text-sm text-slate-500">{video.description}</p>
                <dl className="mt-4 text-sm">
                  <div className="flex items-center justify-between">
                    <dt className="text-slate-400">등록일</dt>
                    <dd className="font-medium text-slate-800">{video.registered_at}</dd>
                  </div>
                </dl>
                <div className="mt-5 flex gap-2">
                  <button
                    onClick={() => usageMutation.mutate(video)}
                    disabled={usageMutation.isPending || reliefMutation.isPending}
                    className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
                  >
                    <ExternalLink className="h-4 w-4" />
                    영상권한 신청
                  </button>
                  <button
                    onClick={() => reliefMutation.mutate(video)}
                    disabled={usageMutation.isPending || reliefMutation.isPending}
                    className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    권리소명요청
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
          </>
        )}
      </section>
    </div>
  );
}
