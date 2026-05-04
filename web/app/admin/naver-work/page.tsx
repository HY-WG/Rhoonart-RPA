"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// ── 타입 ──────────────────────────────────────────────────────────────────────
interface Applicant {
  applicant_id: string;
  name: string;
  phone_number: string;
  naver_id: string;
  naver_clip_profile_name: string;
  naver_clip_profile_id: string;
  representative_channel_name: string;
  representative_channel_platform: string;
  channel_url: string;
  submitted_at: string;
}

const PLATFORMS = [
  "네이버 클립프로필(네이버 TV 포함)",
  "유튜브",
  "인스타그램",
  "틱톡",
  "카카오톡숏폼",
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── 훅 ───────────────────────────────────────────────────────────────────────
function useApplicants() {
  return useQuery<Applicant[]>({
    queryKey: ["a3-applicants"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/a3/applicants`);
      if (!res.ok) throw new Error(`조회 실패 (HTTP ${res.status})`);
      return res.json();
    },
    staleTime: 30_000,
  });
}

function useCreateApplicant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<Applicant, "applicant_id" | "submitted_at">) => {
      const res = await fetch(`${API_BASE}/api/a3/applicants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "등록 실패");
      }
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["a3-applicants"] }),
  });
}

function useTriggerA3() {
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/api/a3/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: {} }),
      });
      if (!res.ok) throw new Error("A-3 실행 실패");
      return res.json();
    },
  });
}

// ── 신청 폼 ──────────────────────────────────────────────────────────────────
const EMPTY_FORM = {
  name: "",
  phone_number: "",
  naver_id: "",
  naver_clip_profile_name: "",
  naver_clip_profile_id: "",
  representative_channel_name: "",
  representative_channel_platform: PLATFORMS[0],
  channel_url: "",
};

function ApplicantForm({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const create = useCreateApplicant();

  const update = (k: keyof typeof EMPTY_FORM) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResult(null);
    try {
      await create.mutateAsync(form);
      setResult({ ok: true, msg: `${form.name} 신청이 등록되었습니다.` });
      setForm(EMPTY_FORM);
    } catch (err: any) {
      setResult({ ok: false, msg: err.message });
    }
  };

  const fields: { key: keyof typeof EMPTY_FORM; label: string; placeholder?: string }[] = [
    { key: "name", label: "이름", placeholder: "홍길동" },
    { key: "phone_number", label: "전화번호", placeholder: "010-0000-0000" },
    { key: "naver_id", label: "네이버 ID", placeholder: "naver_id" },
    { key: "naver_clip_profile_name", label: "클립 프로필명", placeholder: "채널 표시명" },
    { key: "naver_clip_profile_id", label: "클립 프로필 ID", placeholder: "@profile_id" },
    { key: "representative_channel_name", label: "대표 채널명", placeholder: "채널명" },
    { key: "channel_url", label: "채널 URL", placeholder: "https://..." },
  ];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-700">신규 신청 등록</h2>
        <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">닫기 ×</button>
      </div>
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {fields.map(({ key, label, placeholder }) => (
            <div key={key} className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">{label}</label>
              <input
                required
                value={form[key]}
                onChange={update(key)}
                placeholder={placeholder}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
            </div>
          ))}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">대표 채널 플랫폼</label>
            <select
              value={form.representative_channel_platform}
              onChange={update("representative_channel_platform")}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            >
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-4">
          <button
            type="submit"
            disabled={create.isPending}
            className="px-5 py-2 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 disabled:opacity-50"
          >
            {create.isPending ? "등록 중…" : "등록"}
          </button>
          {result && (
            <p className={`text-sm ${result.ok ? "text-emerald-600" : "text-red-500"}`}>
              {result.ok ? "✓ " : "✗ "}{result.msg}
            </p>
          )}
        </div>
      </form>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────
export default function NaverWorkPage() {
  const [showForm, setShowForm] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const { data: applicants = [], isLoading, error } = useApplicants();
  const triggerA3 = useTriggerA3();

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const handleTrigger = async () => {
    try {
      showToast("A-3 월별 보고서 생성 중…", true);
      await triggerA3.mutateAsync();
      showToast("A-3 실행 완료. 이메일이 발송되었습니다.", true);
    } catch (e: any) {
      showToast(e.message, false);
    }
  };

  return (
    <div className="p-8">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">네이버 클립 채널 인입</h1>
          <p className="text-sm text-gray-400 mt-1">
            매월 네이버에 제출할 신규 채널 신청 목록을 관리합니다.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50"
          >
            {showForm ? "폼 닫기" : "+ 신규 등록"}
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggerA3.isPending}
            className="px-4 py-2 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 disabled:opacity-50"
          >
            {triggerA3.isPending ? "실행 중…" : "월별 보고서 발송"}
          </button>
        </div>
      </div>

      {/* 신규 등록 폼 */}
      {showForm && <ApplicantForm onClose={() => setShowForm(false)} />}

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">이름</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">네이버 ID</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">클립 프로필</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">대표 채널</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">플랫폼</th>
              <th className="px-5 py-3.5 text-left text-xs text-gray-500 font-semibold uppercase">신청일</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-sm text-gray-400">불러오는 중…</td></tr>
            )}
            {!isLoading && error && (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-sm text-red-400">
                오류: {(error as Error).message}
              </td></tr>
            )}
            {!isLoading && !error && applicants.length === 0 && (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-sm text-gray-400">
                등록된 신청이 없습니다.
              </td></tr>
            )}
            {applicants.map((a) => (
              <tr key={a.applicant_id} className="border-b border-gray-50 hover:bg-gray-50/60 transition-colors">
                <td className="px-5 py-3.5 text-sm font-medium text-gray-900">{a.name}</td>
                <td className="px-5 py-3.5 text-sm text-gray-600">{a.naver_id}</td>
                <td className="px-5 py-3.5">
                  <p className="text-sm text-gray-700">{a.naver_clip_profile_name}</p>
                  <p className="text-xs text-gray-400">{a.naver_clip_profile_id}</p>
                </td>
                <td className="px-5 py-3.5">
                  <a
                    href={a.channel_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-teal-600 hover:underline"
                  >
                    {a.representative_channel_name}
                  </a>
                </td>
                <td className="px-5 py-3.5 text-xs text-gray-500">{a.representative_channel_platform}</td>
                <td className="px-5 py-3.5 text-sm text-gray-500">
                  {a.submitted_at ? a.submitted_at.slice(0, 10) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium ${
          toast.ok ? "bg-gray-900 text-white" : "bg-red-500 text-white"
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
