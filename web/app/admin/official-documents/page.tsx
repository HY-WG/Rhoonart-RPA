"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  ChevronLeft,
  FilePenLine,
  Italic,
  Save,
} from "lucide-react";
import {
  fetchOfficialDocument,
  fetchOfficialDocumentHolders,
  saveOfficialDocument,
  type OfficialDocument,
} from "@/lib/api";

// ── Rich text toolbar ───────────────────────────────────────────────────────

const FONT_SIZES = ["12px", "14px", "16px", "18px", "20px", "24px"];

function ToolbarButton({
  title,
  active,
  onClick,
  children,
}: {
  title: string;
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onMouseDown={(e) => {
        e.preventDefault();
        onClick();
      }}
      className={`flex h-7 w-7 items-center justify-center rounded text-sm transition-colors ${
        active
          ? "bg-blue-100 text-blue-700"
          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
      }`}
    >
      {children}
    </button>
  );
}

function RichTextEditor({
  html,
  onChange,
}: {
  html: string;
  onChange: (html: string) => void;
}) {
  const editorRef = useRef<HTMLDivElement>(null);
  const [activeFormats, setActiveFormats] = useState({ bold: false, italic: false });
  const [fontSize, setFontSize] = useState("14px");
  const isSettingRef = useRef(false);

  // Sync external html → editor only on holder change (avoid caret reset on every keystroke)
  useEffect(() => {
    if (!editorRef.current) return;
    if (editorRef.current.innerHTML === html) return;
    isSettingRef.current = true;
    editorRef.current.innerHTML = html;
    isSettingRef.current = false;
  }, [html]);

  const exec = useCallback((command: string, value?: string) => {
    document.execCommand(command, false, value);
    editorRef.current?.focus();
    if (editorRef.current) onChange(editorRef.current.innerHTML);
  }, [onChange]);

  const updateToolbarState = useCallback(() => {
    setActiveFormats({
      bold: document.queryCommandState("bold"),
      italic: document.queryCommandState("italic"),
    });
  }, []);

  const handleInput = () => {
    if (isSettingRef.current) return;
    if (editorRef.current) onChange(editorRef.current.innerHTML);
    updateToolbarState();
  };

  const insertPlaceholder = () => {
    exec("insertHTML", '<span class="placeholder-tag" contenteditable="false" style="background:#dbeafe;color:#1d4ed8;border-radius:4px;padding:1px 6px;font-family:monospace;font-size:12px;user-select:none;">{{work_list_table}}</span>&#8203;');
  };

  return (
    <div className="overflow-hidden rounded-md border border-slate-300 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 bg-slate-50 px-2 py-1.5">
        <ToolbarButton title="굵게 (Bold)" active={activeFormats.bold} onClick={() => exec("bold")}>
          <Bold className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="기울임 (Italic)" active={activeFormats.italic} onClick={() => exec("italic")}>
          <Italic className="h-3.5 w-3.5" />
        </ToolbarButton>

        <div className="mx-1 h-5 w-px bg-slate-300" />

        <ToolbarButton title="왼쪽 정렬" onClick={() => exec("justifyLeft")}>
          <AlignLeft className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="가운데 정렬" onClick={() => exec("justifyCenter")}>
          <AlignCenter className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="오른쪽 정렬" onClick={() => exec("justifyRight")}>
          <AlignRight className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="양쪽 정렬" onClick={() => exec("justifyFull")}>
          <AlignJustify className="h-3.5 w-3.5" />
        </ToolbarButton>

        <div className="mx-1 h-5 w-px bg-slate-300" />

        <select
          title="글자 크기"
          value={fontSize}
          onChange={(e) => {
            setFontSize(e.target.value);
            exec("fontSize", "7");
            // execCommand fontSize only takes 1-7; override via span style instead
            const selection = window.getSelection();
            if (selection && !selection.isCollapsed) {
              document.execCommand("styleWithCSS", false, "true");
              document.execCommand("fontSize", false, e.target.value);
            }
          }}
          onMouseDown={(e) => e.preventDefault()}
          className="h-7 rounded border border-slate-200 bg-white px-1 text-xs text-slate-700 focus:outline-none"
        >
          {FONT_SIZES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <div className="mx-1 h-5 w-px bg-slate-300" />

        <button
          type="button"
          title="작품 목록 표 치환자 삽입"
          onMouseDown={(e) => {
            e.preventDefault();
            insertPlaceholder();
          }}
          className="flex h-7 items-center gap-1 rounded border border-blue-200 bg-blue-50 px-2 text-xs font-medium text-blue-700 hover:bg-blue-100"
        >
          {"{{work_list_table}}"}
        </button>
      </div>

      {/* Editor area */}
      <div
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        onKeyUp={updateToolbarState}
        onMouseUp={updateToolbarState}
        style={{ minHeight: "360px", outline: "none" }}
        className="px-4 py-3 text-sm leading-7 text-slate-900"
      />
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

function AdminOfficialDocumentsContent() {
  const searchParams = useSearchParams();
  const initialRightHolderId = searchParams.get("rightHolderId") ?? "";
  const initialWorkId        = searchParams.get("workId") ?? "";
  const initialWorkTitle     = searchParams.get("workTitle") ?? "";
  const initialRightHolderName = searchParams.get("rightHolderName") ?? "";
  // 저작권 소명 목록에서 넘어온 경우 — 뒤로가기 버튼 표시 여부
  const fromClaims = Boolean(initialRightHolderId && initialWorkId);

  const queryClient = useQueryClient();
  const [selectedHolderId, setSelectedHolderId] = useState(initialRightHolderId);
  const [selectedWorkId, setSelectedWorkId]     = useState(initialWorkId);
  const [title, setTitle]         = useState("");
  const [body, setBody]           = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  // workId가 URL에 있을 때는 해당 작품 제목으로 필터 초기화 → 목록에서 즉시 보임
  const [workFilter, setWorkFilter] = useState(initialWorkId ? initialWorkTitle : "");

  // 선택된 작품으로 자동 스크롤하기 위한 ref
  const selectedWorkRef = useRef<HTMLDivElement>(null);

  const holdersQuery = useQuery({
    queryKey: ["official-document-holders"],
    queryFn: fetchOfficialDocumentHolders,
  });

  const documentQuery = useQuery<OfficialDocument>({
    queryKey: ["official-document", selectedHolderId, selectedWorkId],
    queryFn: () => fetchOfficialDocument(selectedHolderId, selectedWorkId),
    enabled: Boolean(selectedHolderId && selectedWorkId),
  });

  const selectedHolderName = useMemo(() => {
    return holdersQuery.data?.items.find((h) => h.right_holder_id === selectedHolderId)
      ?.right_holder_name;
  }, [holdersQuery.data?.items, selectedHolderId]);

  const selectedHolder = useMemo(() => {
    return holdersQuery.data?.items.find((h) => h.right_holder_id === selectedHolderId);
  }, [holdersQuery.data?.items, selectedHolderId]);

  const selectedWorkTitle = useMemo(() => {
    return selectedHolder?.works?.find((work) => work.work_id === selectedWorkId)?.work_title;
  }, [selectedHolder?.works, selectedWorkId]);

  const filteredWorks = useMemo(() => {
    const keyword = workFilter.trim().toLowerCase();
    const works = selectedHolder?.works ?? [];
    if (!keyword) return works;
    return works.filter((work) => work.work_title.toLowerCase().includes(keyword));
  }, [selectedHolder?.works, workFilter]);

  useEffect(() => {
    if (!documentQuery.data) return;
    setTitle(documentQuery.data.content_body.title ?? "");
    setBody(documentQuery.data.content_body.body ?? "");
    setSaveMessage("");
  }, [documentQuery.data]);

  // 권리사 데이터가 로드된 후 선택된 work로 스크롤
  useEffect(() => {
    if (!selectedWorkId || !selectedHolder) return;
    const timer = setTimeout(() => {
      selectedWorkRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, 120);
    return () => clearTimeout(timer);
  }, [selectedHolder, selectedWorkId]);

  const saveMutation = useMutation({
    mutationFn: () => saveOfficialDocument(selectedHolderId, { title, body }, selectedWorkId),
    onSuccess: () => {
      setSaveMessage("저장되었습니다.");
      queryClient.invalidateQueries({ queryKey: ["official-document-holders"] });
      queryClient.invalidateQueries({ queryKey: ["official-document", selectedHolderId, selectedWorkId] });
    },
    onError: (error) => {
      setSaveMessage((error as Error).message);
    },
  });

  return (
    <div className="grid min-h-full grid-cols-[320px_minmax(0,1fr)]">
      <aside className="border-r border-slate-200 bg-white p-6">
        <div className="mb-5">
          {/* 저작권 소명 목록에서 넘어온 경우 뒤로가기 링크 */}
          {fromClaims && (
            <Link
              href="/admin/copyright-claims"
              className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-blue-700"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              저작권 소명 목록으로
            </Link>
          )}
          <h1 className="text-2xl font-bold text-slate-950">공문 작성</h1>
          <p className="mt-1 text-sm text-slate-500">권리사를 선택한 뒤 작품별 공문을 작성합니다.</p>
        </div>

        {holdersQuery.data?.fallback && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            DB 테이블 적용 전이라 샘플 권리사를 표시합니다.
          </div>
        )}

        <div className="space-y-2">
          {holdersQuery.isLoading && <p className="text-sm text-slate-500">불러오는 중입니다.</p>}
          {(holdersQuery.data?.items ?? []).map((holder) => (
            <button
              key={holder.right_holder_id}
              type="button"
              onClick={() => {
                setSelectedHolderId(holder.right_holder_id);
                setSelectedWorkId("");
                setWorkFilter("");
                setSaveMessage("");
              }}
              className={`flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm ${
                selectedHolderId === holder.right_holder_id
                  ? "border-blue-300 bg-blue-50 text-blue-800"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate font-semibold">{holder.right_holder_name}</span>
                <span className="text-xs text-slate-500">
                  작품 {holder.works?.length ?? 0}개 · {holder.has_document ? "저장된 공문 있음" : "공문 없음"}
                </span>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="grid grid-cols-[360px_minmax(0,1fr)] gap-6 p-8">
        {!selectedHolderId && (
          <section className="col-span-2 rounded-lg border border-slate-200 bg-white p-10 text-center text-slate-500">
            왼쪽 목록에서 권리사를 선택하세요.
          </section>
        )}

        {selectedHolderId && (
          <>
          <aside className="rounded-lg border border-slate-200 bg-white p-5">
            {/* 소명 목록에서 이동한 경우: 필터 컨텍스트 배너 */}
            {fromClaims && (
              <div className="mb-4 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700">
                <p className="font-semibold">{initialRightHolderName || selectedHolderName}</p>
                <p className="mt-0.5 text-blue-500">{initialWorkTitle} 공문 작성 화면</p>
              </div>
            )}

            <h2 className="text-sm font-bold text-slate-950">{selectedHolderName} 작품</h2>
            <input
              value={workFilter}
              onChange={(event) => setWorkFilter(event.target.value)}
              placeholder="작품 검색"
              className="mt-3 h-9 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
            <div className="mt-4 max-h-[680px] space-y-2 overflow-y-auto">
              {filteredWorks.length === 0 && (
                <p className="rounded-md bg-slate-50 px-3 py-8 text-center text-sm text-slate-400">
                  표시할 작품이 없습니다.
                </p>
              )}
              {filteredWorks.map((work) => (
                <div
                  key={work.work_id}
                  ref={work.work_id === selectedWorkId ? selectedWorkRef : null}
                  className={`rounded-md border px-3 py-2 ${
                    selectedWorkId === work.work_id
                      ? "border-blue-300 bg-blue-50 ring-1 ring-blue-200"
                      : "border-slate-200"
                  }`}
                >
                  <p className="truncate text-sm font-semibold text-slate-900">{work.work_title}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-xs text-slate-500">
                      {work.has_document ? "저장된 공문 있음" : "공문 없음"}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedWorkId(work.work_id);
                        setSaveMessage("");
                      }}
                      className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2 py-1 text-xs font-semibold text-white"
                    >
                      <FilePenLine className="h-3.5 w-3.5" />
                      공문 작성
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </aside>
          <section className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-slate-950">
                  {selectedWorkTitle ?? documentQuery.data?.work_title ?? "작품"} 공문
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {selectedHolderName ?? documentQuery.data?.right_holder_name ?? "권리사"} 소유 작품 기준으로 저장됩니다.
                </p>
              </div>
              <button
                type="button"
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending || documentQuery.isLoading || !selectedWorkId}
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save className="h-4 w-4" />
                저장
              </button>
            </div>

            {documentQuery.data?.fallback && (
              <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                저장된 공문이 없어 기본 문안으로 시작합니다.
              </div>
            )}

            {saveMessage && (
              <div
                className={`mb-4 rounded-md px-4 py-3 text-sm ${
                  saveMessage === "저장되었습니다."
                    ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border border-red-200 bg-red-50 text-red-700"
                }`}
              >
                {saveMessage}
              </div>
            )}

            <div className="space-y-4">
              {!selectedWorkId && (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  왼쪽 작품 리스트에서 공문을 작성할 작품을 선택하세요.
                </div>
              )}
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">제목</span>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <div>
                <span className="mb-1 block text-sm font-semibold text-slate-700">본문</span>
                {selectedWorkId && !documentQuery.isLoading && (
                  <RichTextEditor html={body} onChange={setBody} />
                )}
              </div>
            </div>
          </section>
          </>
        )}
      </main>
    </div>
  );
}

export default function AdminOfficialDocumentsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-500">공문 작성 화면을 불러오는 중입니다.</div>}>
      <AdminOfficialDocumentsContent />
    </Suspense>
  );
}
