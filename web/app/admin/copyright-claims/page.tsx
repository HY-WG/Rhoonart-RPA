"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Eye, FilePenLine, Send, X } from "lucide-react";
import {
  fetchCopyrightClaims,
  fetchOfficialDocument,
  requestCopyrightClaim,
  sendChannelClaimEmail,
  type CopyrightClaimItem,
} from "@/lib/api";

function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

// ── 공문 미리보기 모달 ────────────────────────────────────────────────────────
function DocumentPreviewModal({
  rightHolderId,
  rightHolderName,
  workId,
  workTitle,
  onClose,
}: {
  rightHolderId: string;
  rightHolderName: string;
  workId: string;
  workTitle: string;
  onClose: () => void;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["official-document", rightHolderId, workId],
    queryFn: () => fetchOfficialDocument(rightHolderId, workId),
    enabled: !!rightHolderId,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex w-full max-w-2xl flex-col rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">공문 미리보기</h2>
            <p className="mt-0.5 text-xs text-slate-500">{rightHolderName} · {workTitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-6 py-5">
          {isLoading && <p className="text-sm text-slate-400">불러오는 중입니다...</p>}
          {error && (
            <p className="text-sm text-red-500">
              공문을 불러오는데 실패했습니다. {(error as Error).message}
            </p>
          )}
          {data && !data.fallback && (
            <>
              {data.content_body?.title && (
                <h3 className="mb-3 text-sm font-semibold text-slate-900">
                  {data.content_body.title}
                </h3>
              )}
              {data.content_body?.body ? (
                <div
                  className="prose prose-sm max-w-none text-slate-700"
                  dangerouslySetInnerHTML={{ __html: data.content_body.body }}
                />
              ) : (
                <p className="text-sm text-slate-400">공문 내용이 없습니다.</p>
              )}
            </>
          )}
          {data?.fallback && (
            <p className="text-sm text-slate-400">
              해당 소명에 등록된 공문이 없습니다. 권리자 &gt; 공문 작성 페이지에서 직접 공문을 작성해주세요.
            </p>
          )}
        </div>
        <div className="flex justify-end border-t border-slate-100 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 채널 발송 확인 모달 ────────────────────────────────────────────────────────
function ChannelSendModal({
  channelName,
  claims,
  onConfirm,
  onClose,
  isPending,
}: {
  channelName: string;
  claims: CopyrightClaimItem[];
  onConfirm: () => void;
  onClose: () => void;
  isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-900">채널 메일로 발송</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm text-slate-700">
            <span className="font-semibold">{channelName}</span> 채널에 등록된 작품들의 권리자에게
            일괄 메일로 발송합니다.
          </p>
          <ul className="mt-3 space-y-1">
            {claims.map((claim) => (
              <li key={claim.id} className="flex items-center gap-2 text-sm text-slate-600">
                <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
                {claim.work_title}
                <span className="text-xs text-slate-400">({claim.right_holder_name})</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Send className="h-3.5 w-3.5" />
            {isPending ? "발송 중..." : "발송"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 공문 없음 안내 모달 ───────────────────────────────────────────────────────
function NoDocumentModal({
  claim,
  onClose,
}: {
  claim: CopyrightClaimItem;
  onClose: () => void;
}) {
  const docHref =
    `/admin/official-documents` +
    `?rightHolderId=${encodeURIComponent(claim.right_holder_id)}` +
    `&workId=${encodeURIComponent(claim.work_id)}` +
    `&workTitle=${encodeURIComponent(claim.work_title)}` +
    `&rightHolderName=${encodeURIComponent(claim.right_holder_name)}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-900">소명 요청 불가</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm text-slate-700">
            해당 권리사는 이전 소명 진행 이력이 없습니다.{" "}
            <span className="font-semibold">공문을 먼저 작성해주세요.</span>
          </p>
          <p className="mt-2 text-xs text-slate-500">
            <span className="font-medium">{claim.right_holder_name}</span> ·{" "}
            {claim.work_title}
          </p>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            닫기
          </button>
          <Link
            href={docHref}
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
          >
            <FilePenLine className="h-3.5 w-3.5" />
            공문 작성하기
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── 메인 페이지 ──────────────────────────────────────────────────────────────
export default function AdminCopyrightClaimsPage() {
  const queryClient = useQueryClient();
  const [previewClaim, setPreviewClaim] = useState<CopyrightClaimItem | null>(null);
  const [noDocClaim, setNoDocClaim] = useState<CopyrightClaimItem | null>(null);
  const [channelSend, setChannelSend] = useState<{
    channelId: string;
    channelName: string;
    claims: CopyrightClaimItem[];
  } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-copyright-claims"],
    queryFn: fetchCopyrightClaims,
  });

  const requestMutation = useMutation({
    mutationFn: (claim: CopyrightClaimItem) =>
      requestCopyrightClaim(claim.right_holder_id, claim.work_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-copyright-claims"] });
    },
  });

  /** "요청" 버튼 클릭 — 공문 없으면 안내 모달, 있으면 API 호출 */
  function handleRequestClick(claim: CopyrightClaimItem) {
    if (!claim.has_admin_official_document) {
      setNoDocClaim(claim);
      return;
    }
    requestMutation.mutate(claim);
  }

  const sendEmailMutation = useMutation({
    mutationFn: ({ channelId, claimIds }: { channelId: string; claimIds: string[] }) =>
      sendChannelClaimEmail(channelId, claimIds),
    onSuccess: (result) => {
      window.alert(result.message);
      setChannelSend(null);
    },
    onError: (err) => {
      window.alert(`발송 실패: ${(err as Error).message}`);
    },
  });

  const claims = [...(data?.items ?? [])].sort((a, b) => {
    const aDoc = a.has_official_document ? 1 : 0;
    const bDoc = b.has_official_document ? 1 : 0;
    if (aDoc !== bDoc) return aDoc - bDoc;
    return String(b.requested_at ?? "").localeCompare(String(a.requested_at ?? ""));
  });

  // channel_id 기준으로 묶인 claims를 그룹화(채널 발송 시 일괄 메일용)
  const claimsByChannel = (data?.items ?? []).reduce<Record<string, CopyrightClaimItem[]>>(
    (acc, claim) => {
      const key = claim.channel_id;
      if (!acc[key]) acc[key] = [];
      acc[key].push(claim);
      return acc;
    },
    {}
  );

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-950">저작권 소명 요청 리스트</h1>
        <p className="mt-1 text-sm text-slate-500">
          전체 등록된 작품들의 요청 상태를 표시합니다. 권리자의 공문을 확인 후 채널에 일괄 메일로 발송해주세요.
        </p>
      </div>

      {data?.fallback && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          DB 데이터가 아직 적용되지 않아 샘플 데이터로 화면을 표시하고 있습니다.
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          요청 목록을 불러오는데 실패했습니다. {(error as Error).message}
        </div>
      )}

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[1060px] text-sm">
          <thead className="bg-slate-50">
            <tr className="border-b border-slate-200">
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                채널
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                작품
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                요청일자
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                권리자
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                상태
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                권리자 요청
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                권리자 공문
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                채널 발송
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                  불러오는 중입니다.
                </td>
              </tr>
            )}
            {!isLoading && claims.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                  처리 중인 상태이거나 아직 요청 건이 없습니다.
                </td>
              </tr>
            )}
            {claims.map((claim) => {
                // 채널의 모든 claim 목록 (일괄 메일 발송용)
                const channelClaims = claimsByChannel[claim.channel_id] ?? [claim];
                const hasDocument = Boolean(claim.has_official_document);
                const docStatus = claim.official_document_status ?? "not_requested";

                return (
                  <tr
                    key={claim.id}
                    className={`hover:bg-slate-50/70 ${hasDocument ? "bg-emerald-50/30" : ""}`}
                  >
                    <td className="px-4 py-4 font-medium text-slate-900">
                      {claim.channel_name}
                    </td>

                    <td className="px-4 py-4 text-slate-700">
                      <Link
                        href={`/admin/official-documents?rightHolderId=${encodeURIComponent(claim.right_holder_id)}&workId=${encodeURIComponent(claim.work_id)}`}
                        className="font-semibold text-blue-700 hover:underline"
                      >
                        {claim.work_title}
                      </Link>
                    </td>

                    <td className="px-4 py-4 text-slate-600">{formatDate(claim.requested_at)}</td>

                    <td className="px-4 py-4 font-semibold text-slate-900">
                      {claim.right_holder_name}
                    </td>

                    <td className="px-4 py-4">
                      {hasDocument ? (
                        <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                          공문 저장됨
                        </span>
                      ) : (
                        <Link
                          href={`/admin/official-documents?rightHolderId=${encodeURIComponent(claim.right_holder_id)}&workId=${encodeURIComponent(claim.work_id)}&workTitle=${encodeURIComponent(claim.work_title)}&rightHolderName=${encodeURIComponent(claim.right_holder_name)}`}
                          className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-blue-50 hover:text-blue-700"
                        >
                          공문 없음
                        </Link>
                      )}
                    </td>

                    {/* 권리자 요청 — 상태에 따라 버튼 / 배지로 분기 */}
                    <td className="px-4 py-4">
                      {docStatus === "received" || hasDocument ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          접수 완료
                        </span>
                      ) : docStatus === "requested" ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          요청 완료
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleRequestClick(claim)}
                          disabled={requestMutation.isPending}
                          className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Send className="h-3.5 w-3.5" />
                          요청
                        </button>
                      )}
                    </td>

                    <td className="px-4 py-4">
                      <button
                        type="button"
                        onClick={() => setPreviewClaim(claim)}
                        disabled={!hasDocument}
                        className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        확인
                      </button>
                    </td>

                    <td className="px-4 py-4 align-middle">
                      {channelClaims[0]?.id === claim.id ? (
                        <button
                          type="button"
                          onClick={() =>
                            setChannelSend({
                              channelId: claim.channel_id,
                              channelName: claim.channel_name,
                              claims: channelClaims,
                            })
                          }
                          className="inline-flex items-center gap-1.5 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-teal-700 hover:bg-teal-100"
                        >
                          <Send className="h-3.5 w-3.5" />
                          발송
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </td>
                  </tr>
                );
            })}
          </tbody>
        </table>
      </section>

      {/* 공문 없음 안내 모달 */}
      {noDocClaim && (
        <NoDocumentModal claim={noDocClaim} onClose={() => setNoDocClaim(null)} />
      )}

      {/* 공문 미리보기 모달 */}
      {previewClaim && (
        <DocumentPreviewModal
          rightHolderId={previewClaim.right_holder_id}
          rightHolderName={previewClaim.right_holder_name}
          workId={previewClaim.work_id}
          workTitle={previewClaim.work_title}
          onClose={() => setPreviewClaim(null)}
        />
      )}

      {/* 채널 발송 확인 모달 */}
      {channelSend && (
        <ChannelSendModal
          channelName={channelSend.channelName}
          claims={channelSend.claims}
          isPending={sendEmailMutation.isPending}
          onConfirm={() =>
            sendEmailMutation.mutate({
              channelId: channelSend.channelId,
              claimIds: channelSend.claims.map((c) => c.id),
            })
          }
          onClose={() => setChannelSend(null)}
        />
      )}
    </div>
  );
}
