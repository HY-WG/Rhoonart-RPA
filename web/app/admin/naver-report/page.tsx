"use client";

import { useState, useEffect, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { X, Send, ChevronRight } from "lucide-react";

/* ──────────────────────────────────────────
   타입
────────────────────────────────────────── */
type RightsHolder = { id: string; name: string; email: string };
type FilterState = {
  dateFrom: string;
  dateTo: string;
  channel: string;
  workCode: string;
  clip: string;
};

/* ──────────────────────────────────────────
   Looker URL 빌더
────────────────────────────────────────── */
const BASE_LOOKER_URL =
  process.env.NEXT_PUBLIC_LOOKER_URL ??
  "https://lookerstudio.google.com/embed/reporting/REPLACE_ME/page/p_example";

function buildLookerUrl(f: FilterState): string {
  const params = new URLSearchParams();
  if (f.dateFrom) params.set("df2", `${f.dateFrom}`);
  if (f.dateTo)   params.set("dt2", `${f.dateTo}`);
  if (f.channel)  params.set("channel", f.channel);
  if (f.workCode) params.set("work_code", f.workCode);
  if (f.clip)     params.set("clip", f.clip);
  const qs = params.toString();
  return qs ? `${BASE_LOOKER_URL}&${qs}` : BASE_LOOKER_URL;
}

/* ──────────────────────────────────────────
   메인 컴포넌트
────────────────────────────────────────── */
export default function NaverReportPage() {
  const [filter, setFilter] = useState<FilterState>({
    dateFrom: "", dateTo: "", channel: "", workCode: "", clip: "",
  });
  const [lookerUrl, setLookerUrl] = useState(BASE_LOOKER_URL);
  const [channels, setChannels] = useState<{ id: string; channel_name: string }[]>([]);

  // 권리사 사이드바
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [rightsHolders, setRightsHolders] = useState<RightsHolder[]>([]);
  const [loadingRH, setLoadingRH] = useState(false);

  // 이메일 확인 팝업
  const [confirmTarget, setConfirmTarget] = useState<RightsHolder | null>(null);
  const [sending, setSending] = useState(false);
  const [sentMsg, setSentMsg] = useState("");

  /* 채널 목록 로드 */
  useEffect(() => {
    createClient()
      .from("channel_approvals")
      .select("id, channel_name")
      .eq("status", "approved")
      .then(({ data }) => setChannels(data ?? []));
  }, []);

  /* 필터 변경 시 Looker URL 갱신 */
  const applyFilter = useCallback(() => {
    setLookerUrl(buildLookerUrl(filter));
  }, [filter]);

  /* 권리사 목록 로드 */
  const openSidebar = async () => {
    setSidebarOpen(true);
    if (rightsHolders.length > 0) return;
    setLoadingRH(true);
    const { data } = await createClient()
      .from("rights_holders")
      .select("id, name, email")
      .order("name");
    setRightsHolders(
      data && data.length > 0
        ? data
        : [
            { id: "1", name: "웨이브", email: "wavve@rights.co.kr" },
            { id: "2", name: "판씨네마", email: "pans@rights.co.kr" },
            { id: "3", name: "영상권리사", email: "rights@rights.co.kr" },
          ]
    );
    setLoadingRH(false);
  };

  /* 이메일 발송 */
  const handleSend = async () => {
    if (!confirmTarget) return;
    setSending(true);
    await new Promise((r) => setTimeout(r, 800)); // API 호출 자리
    setSending(false);
    setSentMsg(`${confirmTarget.name} (${confirmTarget.email}) 으로 보고서를 발송했습니다.`);
    setConfirmTarget(null);
  };

  return (
    <div className="flex h-full min-h-0 relative">
      {/* ── 메인 영역 ── */}
      <div className="flex-1 p-8 overflow-auto">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">네이버 월별 성과보고</h1>
          <button
            onClick={openSidebar}
            className="flex items-center gap-2 px-5 py-2.5 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 transition-colors"
          >
            권리사 보고
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* 성공 메시지 */}
        {sentMsg && (
          <div className="mb-4 px-4 py-3 bg-teal-50 border border-teal-200 text-teal-700 text-sm rounded-lg flex items-center justify-between">
            <span>✓ {sentMsg}</span>
            <button onClick={() => setSentMsg("")} className="ml-4 text-teal-400 hover:text-teal-600">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* 필터 바 */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">필터</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* 기간 */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">시작일</label>
              <input
                type="date"
                value={filter.dateFrom}
                onChange={(e) => setFilter((f) => ({ ...f, dateFrom: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">종료일</label>
              <input
                type="date"
                value={filter.dateTo}
                onChange={(e) => setFilter((f) => ({ ...f, dateTo: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
            </div>

            {/* 채널별 */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">채널</label>
              <select
                value={filter.channel}
                onChange={(e) => setFilter((f) => ({ ...f, channel: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-400"
              >
                <option value="">전체</option>
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.channel_name}>{ch.channel_name}</option>
                ))}
              </select>
            </div>

            {/* 작품 코드별 */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">작품 코드</label>
              <input
                type="text"
                value={filter.workCode}
                onChange={(e) => setFilter((f) => ({ ...f, workCode: e.target.value }))}
                placeholder="NVR-2026-001"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
            </div>

            {/* 클립별 */}
            <div className="md:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">클립</label>
              <input
                type="text"
                value={filter.clip}
                onChange={(e) => setFilter((f) => ({ ...f, clip: e.target.value }))}
                placeholder="클립 ID 또는 제목"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
            </div>

            {/* 적용 버튼 */}
            <div className="md:col-span-2 flex items-end">
              <button
                onClick={applyFilter}
                className="w-full py-2 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 transition-colors"
              >
                필터 적용
              </button>
            </div>
          </div>
        </div>

        {/* Looker Studio 미리보기 */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Looker Studio 리포트</span>
            <a
              href={lookerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-teal-600 hover:underline"
            >
              새 탭에서 열기 →
            </a>
          </div>
          <iframe
            src={lookerUrl}
            className="w-full"
            style={{ height: "600px", border: "none" }}
            allowFullScreen
            title="Looker Studio Report"
          />
        </div>
      </div>

      {/* ── 권리사 사이드바 ── */}
      <div
        className={`fixed top-0 right-0 h-full w-80 bg-white border-l border-gray-200 shadow-xl z-40 transition-transform duration-300 ${
          sidebarOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">권리사 보고</h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-4 py-4 overflow-y-auto h-[calc(100%-72px)]">
          {loadingRH ? (
            <p className="text-sm text-gray-400 text-center py-8">불러오는 중...</p>
          ) : (
            <div className="space-y-2">
              {rightsHolders.map((rh) => (
                <button
                  key={rh.id}
                  onClick={() => setConfirmTarget(rh)}
                  className="w-full flex items-center justify-between px-4 py-3.5 rounded-xl border border-gray-200 hover:border-teal-300 hover:bg-teal-50 transition-colors group text-left"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-800 group-hover:text-teal-700">
                      {rh.name}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">{rh.email}</p>
                  </div>
                  <Send className="w-4 h-4 text-gray-300 group-hover:text-teal-500 shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 사이드바 오버레이 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-30"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── 이메일 전송 확인 팝업 ── */}
      {confirmTarget && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-2">이메일 발송 확인</h3>
            <p className="text-sm text-gray-500 mb-6">
              아래 권리사에게 성과 보고서를 이메일로 발송합니다.
            </p>

            <div className="bg-gray-50 rounded-xl px-5 py-4 mb-6">
              <p className="text-sm font-semibold text-gray-800">{confirmTarget.name}</p>
              <p className="text-sm text-gray-500 mt-0.5">{confirmTarget.email}</p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setConfirmTarget(null)}
                className="flex-1 py-2.5 border border-gray-300 text-sm text-gray-600 rounded-xl hover:bg-gray-50 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleSend}
                disabled={sending}
                className="flex-1 py-2.5 bg-teal-500 text-white text-sm font-semibold rounded-xl hover:bg-teal-600 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                {sending ? (
                  "발송 중..."
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    이메일 발송
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
