"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Printer, Search, Upload, X } from "lucide-react";
import {
  fetchPartnerOfficialDocument,
  fetchPartnerCopyrightClaims,
  uploadPartnerOfficialDocumentFile,
  type CopyrightClaimItem,
  type OfficialDocument,
} from "@/lib/api";

// ── 파트너 고정 설정 ──────────────────────────────────────────────────────────
const PARTNER_HOLDER_NAME = "CJ";

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDue(claim: CopyrightClaimItem) {
  if (claim.due) return claim.due;
  if (!claim.requested_at) return "-";
  const date = new Date(claim.requested_at);
  if (Number.isNaN(date.getTime())) return "-";
  date.setDate(date.getDate() + 7);
  return date.toISOString().slice(0, 10);
}

function renderDocumentHtml(
  rawHtml: string | undefined,
  claims: CopyrightClaimItem[],
): string {
  const tableRows = claims
    .map(
      (c) =>
        `<tr>
          <td style="border:1px solid #cbd5e1;padding:6px 10px">${c.channel_name}</td>
          <td style="border:1px solid #cbd5e1;padding:6px 10px">${c.work_title}</td>
          <td style="border:1px solid #cbd5e1;padding:6px 10px">${formatDue(c)}</td>
        </tr>`,
    )
    .join("");

  const table =
    claims.length === 0
      ? `<p style="color:#64748b;text-align:center;padding:16px">선택된 작품이 없습니다.</p>`
      : `<table style="width:100%;border-collapse:collapse;font-size:14px">
          <thead>
            <tr style="background:#f8fafc">
              <th style="border:1px solid #cbd5e1;padding:6px 10px;text-align:left">채널</th>
              <th style="border:1px solid #cbd5e1;padding:6px 10px;text-align:left">작품</th>
              <th style="border:1px solid #cbd5e1;padding:6px 10px;text-align:left">마감기한</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>`;

  if (!rawHtml) return table;
  return rawHtml.includes("{{work_list_table}}")
    ? rawHtml.replace(/\{\{work_list_table\}\}/g, table)
    : `${rawHtml}<div style="margin-top:24px">${table}</div>`;
}

// ── Channel group ─────────────────────────────────────────────────────────────

interface ChannelGroup {
  channel_id: string;
  channel_name: string;
  right_holder_id: string;
  work_id: string;
  work_title: string;
  claims: CopyrightClaimItem[];
}

function groupByWorkAndChannel(claims: CopyrightClaimItem[]): ChannelGroup[] {
  return claims.map((claim) => ({
    channel_id: claim.channel_id,
    channel_name: claim.channel_name,
    right_holder_id: claim.right_holder_id,
    work_id: claim.work_id,
    work_title: claim.work_title,
    claims: [claim],
  }));
}

// ── Document modal ────────────────────────────────────────────────────────────

function DocumentModal({
  group,
  cjRightHolderId,
  onClose,
}: {
  group: ChannelGroup;
  cjRightHolderId: string;
  onClose: () => void;
}) {
  const documentQuery = useQuery<OfficialDocument>({
    queryKey: ["partner-official-document", cjRightHolderId, group.work_id],
    queryFn: () => fetchPartnerOfficialDocument(cjRightHolderId, group.work_id),
    enabled: Boolean(cjRightHolderId),
  });

  const renderedHtml = useMemo(
    () => renderDocumentHtml(documentQuery.data?.content_body?.body, group.claims),
    [documentQuery.data, group.claims],
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4 print:hidden">
          <div>
            <h2 className="text-lg font-bold text-slate-950">공문 미리보기</h2>
            <p className="text-sm text-slate-500">
              {group.channel_name} · {group.claims.length}건
              <span className="ml-2 text-slate-400">{group.work_title}</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <Printer className="h-4 w-4" />
              프린트
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="닫기"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto p-6">
          {documentQuery.isLoading && (
            <p className="text-center text-sm text-slate-500">공문을 불러오는 중입니다.</p>
          )}
          {!documentQuery.isLoading && (
            <>
              {documentQuery.data?.content_body?.title && (
                <h3 className="mb-6 text-center text-2xl font-bold text-slate-950">
                  {documentQuery.data.content_body.title}
                </h3>
              )}
              <article
                className="prose prose-sm max-w-none text-slate-900"
                dangerouslySetInnerHTML={{ __html: renderedHtml }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function UploadModal({
  group,
  onClose,
}: {
  group: ChannelGroup;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("제출할 파일을 선택해주세요.");
      return uploadPartnerOfficialDocumentFile(group.claims.map((claim) => claim.id), file);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["partner-copyright-claims"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-950">공문 파일 제출</h2>
            <p className="mt-1 text-sm text-slate-500">
              {group.channel_name} · {group.claims.length}건
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="닫기"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-slate-700">제출 파일</span>
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>

        {uploadMutation.isError && (
          <p className="mt-3 text-sm text-red-600">{(uploadMutation.error as Error).message}</p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            취소
          </button>
          <button
            type="button"
            disabled={!file || uploadMutation.isPending}
            onClick={() => uploadMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? "업로드 중" : "파일 제출"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PartnerReliefPage() {
  const [modalGroup, setModalGroup] = useState<ChannelGroup | null>(null);
  const [uploadGroup, setUploadGroup] = useState<ChannelGroup | null>(null);
  const [workFilter, setWorkFilter] = useState("");

  const claimsQuery = useQuery({
    queryKey: ["partner-copyright-claims"],
    queryFn: fetchPartnerCopyrightClaims,
  });

  const allClaims = useMemo(() => claimsQuery.data?.items ?? [], [claimsQuery.data?.items]);

  // 해당 권리사 데이터 필터링 — admin이 요청했거나(requested) 파트너가 업로드한(received) 건
  const partnerClaims = useMemo(
    () =>
      allClaims.filter((c) => {
        if (c.right_holder_name !== PARTNER_HOLDER_NAME) return false;
        const status = c.official_document_status ?? "not_requested";
        return status === "requested" || status === "received" || Boolean(c.has_official_document);
      }),
    [allClaims],
  );

  // 권리사의 right_holder_id (첫 번째 클레임에서 추출)
  const partnerRightHolderId = partnerClaims[0]?.right_holder_id ?? "";

  const channelGroups = useMemo(() => groupByWorkAndChannel(partnerClaims), [partnerClaims]);

  // 작품명 필터 적용
  const filteredGroups = useMemo(() => {
    const keyword = workFilter.trim().toLowerCase();
    if (!keyword) return channelGroups;
    return channelGroups.filter((g) => g.work_title.toLowerCase().includes(keyword));
  }, [channelGroups, workFilter]);

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-950">저작권 소명 요청 리스트</h1>
          <span className="rounded-full bg-blue-100 px-3 py-0.5 text-sm font-semibold text-blue-700">
            {PARTNER_HOLDER_NAME}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          요청 대상 작품과 채널을 확인하고 공문을 열람합니다.
        </p>
      </div>

      {claimsQuery.data?.fallback && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          DB 테이블이 아직 적용되지 않아 샘플 데이터로 화면 구조를 표시하고 있습니다.
        </div>
      )}

      {/* 작품명 검색 필터 */}
      <div className="mb-4 flex items-center gap-2">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={workFilter}
            onChange={(e) => setWorkFilter(e.target.value)}
            placeholder="작품명으로 검색"
            className="h-9 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
        </div>
        {workFilter && (
          <button
            type="button"
            onClick={() => setWorkFilter("")}
            className="text-xs font-medium text-slate-400 hover:text-slate-700"
          >
            초기화
          </button>
        )}
        <span className="text-xs text-slate-400">{filteredGroups.length}건</span>
      </div>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50">
            <tr className="border-b border-slate-200">
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                작품
              </th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                채널
              </th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                요청 건수
              </th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                최종 마감
              </th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                상태
              </th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                공문 확인
              </th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                공문 제출
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {claimsQuery.isLoading && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-slate-500">
                  불러오는 중입니다.
                </td>
              </tr>
            )}
            {!claimsQuery.isLoading && filteredGroups.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-slate-500">
                  {workFilter
                    ? `"${workFilter}"에 해당하는 요청이 없습니다.`
                    : `${PARTNER_HOLDER_NAME} 권리사에 해당하는 소명 요청이 없습니다.`}
                </td>
              </tr>
            )}
            {filteredGroups.map((group) => {
              const latestDue = group.claims
                .map((c) => formatDue(c))
                .filter((d) => d !== "-")
                .sort()
                .at(-1) ?? "-";
              // 그룹 내 claim 중 하나라도 received이면 접수 완료 상태로 표시
              const isReceived = group.claims.some(
                (c) =>
                  c.official_document_status === "received" || Boolean(c.has_official_document),
              );
              return (
                <tr key={`${group.channel_id}-${group.work_id}`} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 font-medium text-slate-900">{group.work_title}</td>
                  <td className="px-5 py-4 font-medium text-slate-900">{group.channel_name}</td>
                  <td className="px-5 py-4 text-slate-700">{group.claims.length}건</td>
                  <td className="px-5 py-4 text-slate-600">{latestDue}</td>
                  <td className="px-5 py-4">
                    {isReceived ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        접수 완료
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">
                        처리요망
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    <button
                      type="button"
                      onClick={() => setModalGroup(group)}
                      className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      공문 확인
                    </button>
                  </td>
                  <td className="px-5 py-4">
                    {isReceived ? (
                      <span className="text-xs text-slate-400">제출 완료</span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setUploadGroup(group)}
                        className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        파일 제출
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {modalGroup && (
        <DocumentModal
          group={modalGroup}
          cjRightHolderId={partnerRightHolderId}
          onClose={() => setModalGroup(null)}
        />
      )}
      {uploadGroup && <UploadModal group={uploadGroup} onClose={() => setUploadGroup(null)} />}
    </div>
  );
}
