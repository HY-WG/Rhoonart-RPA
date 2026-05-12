"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createA3Applicant, fetchA3Applicants, triggerA3Report } from "@/lib/api";
import type { A3Applicant, A3ApplicantCreate, A3Platform } from "@/lib/types";

const PLATFORMS: A3Platform[] = [
  "네이버 클립프로필(네이버 TV 포함)",
  "유튜브",
  "인스타그램",
  "틱톡",
  "카카오톡숏폼",
];

const EMPTY_FORM: A3ApplicantCreate = {
  name: "",
  phone_number: "",
  naver_id: "",
  naver_clip_profile_name: "",
  naver_clip_profile_id: "",
  representative_channel_name: "",
  representative_channel_platform: PLATFORMS[0],
  channel_url: "",
};

function useApplicants() {
  return useQuery<A3Applicant[]>({
    queryKey: ["a3-applicants"],
    queryFn: fetchA3Applicants,
    staleTime: 30_000,
  });
}

function ApplicantForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<A3ApplicantCreate>(EMPTY_FORM);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const create = useMutation({
    mutationFn: createA3Applicant,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["a3-applicants"] }),
  });

  const update =
    <K extends keyof A3ApplicantCreate>(key: K) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((prev) => ({ ...prev, [key]: event.target.value as A3ApplicantCreate[K] }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setResult(null);
    try {
      await create.mutateAsync(form);
      setResult({ ok: true, msg: `${form.name} 신청을 등록했습니다.` });
      setForm(EMPTY_FORM);
    } catch (error) {
      setResult({ ok: false, msg: (error as Error).message });
    }
  };

  const fields: Array<{
    key: keyof Omit<A3ApplicantCreate, "representative_channel_platform">;
    label: string;
    placeholder?: string;
  }> = [
    { key: "name", label: "이름", placeholder: "홍길동" },
    { key: "phone_number", label: "전화번호", placeholder: "010-0000-0000" },
    { key: "naver_id", label: "네이버 ID", placeholder: "naver_id" },
    { key: "naver_clip_profile_name", label: "클립 프로필명", placeholder: "채널 표시명" },
    { key: "naver_clip_profile_id", label: "클립 프로필 ID", placeholder: "@profile_id" },
    { key: "representative_channel_name", label: "대표 채널명", placeholder: "채널명" },
    { key: "channel_url", label: "채널 URL", placeholder: "https://..." },
  ];

  return (
    <div className="mb-6 rounded-xl border border-gray-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">신규 신청 등록</h2>
        <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">
          닫기
        </button>
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
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
            </div>
          ))}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">대표 채널 플랫폼</label>
            <select
              value={form.representative_channel_platform}
              onChange={update("representative_channel_platform")}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            >
              {PLATFORMS.map((platform) => (
                <option key={platform} value={platform}>
                  {platform}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-lg bg-teal-500 px-5 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-50"
          >
            {create.isPending ? "등록 중" : "등록"}
          </button>
          {result && (
            <p className={`text-sm ${result.ok ? "text-emerald-600" : "text-red-500"}`}>
              {result.msg}
            </p>
          )}
        </div>
      </form>
    </div>
  );
}

export default function NaverWorkPage() {
  const [showForm, setShowForm] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const { data: applicants = [], isLoading, error } = useApplicants();
  const triggerReport = useMutation({ mutationFn: triggerA3Report });

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const handleTrigger = async () => {
    try {
      showToast("A-3 월별 보고서를 생성 중입니다.", true);
      await triggerReport.mutateAsync();
      showToast("A-3 실행 완료. 이메일 발송을 확인해주세요.", true);
    } catch (error) {
      showToast((error as Error).message, false);
    }
  };

  return (
    <div className="p-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">네이버 클립 채널 인입</h1>
          <p className="mt-1 text-sm text-gray-400">
            네이버 클립 제출 대상 채널 신청 목록을 관리합니다.
          </p>
          {error && (
            <p className="mt-2 max-w-3xl text-xs text-amber-700">
              Failed to fetch가 발생하면 FastAPI 8001 서버 실행 여부, web/.env.local의
              NEXT_PUBLIC_API_BASE, 그리고 X-RPA-Token 헤더 설정을 확인하세요.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm((value) => !value)}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            {showForm ? "등록 닫기" : "+ 신규 등록"}
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggerReport.isPending}
            className="rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-50"
          >
            {triggerReport.isPending ? "실행 중" : "월별 보고서 발송"}
          </button>
        </div>
      </div>

      {showForm && <ApplicantForm onClose={() => setShowForm(false)} />}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-gray-500">이름</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-gray-500">네이버 ID</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-gray-500">클립 프로필</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-gray-500">대표 채널</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-gray-500">플랫폼</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold uppercase text-gray-500">신청일</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-sm text-gray-400">
                  불러오는 중
                </td>
              </tr>
            )}
            {!isLoading && error && (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-sm text-red-500">
                  오류: {(error as Error).message}
                </td>
              </tr>
            )}
            {!isLoading && !error && applicants.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-sm text-gray-400">
                  등록된 신청이 없습니다.
                </td>
              </tr>
            )}
            {applicants.map((applicant) => (
              <tr key={applicant.applicant_id} className="border-b border-gray-50 hover:bg-gray-50/60">
                <td className="px-5 py-3.5 text-sm font-medium text-gray-900">{applicant.name}</td>
                <td className="px-5 py-3.5 text-sm text-gray-600">{applicant.naver_id}</td>
                <td className="px-5 py-3.5">
                  <p className="text-sm text-gray-700">{applicant.naver_clip_profile_name}</p>
                  <p className="text-xs text-gray-400">{applicant.naver_clip_profile_id}</p>
                </td>
                <td className="px-5 py-3.5">
                  <a
                    href={applicant.channel_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-teal-600 hover:underline"
                  >
                    {applicant.representative_channel_name}
                  </a>
                </td>
                <td className="px-5 py-3.5 text-xs text-gray-500">
                  {applicant.representative_channel_platform}
                </td>
                <td className="px-5 py-3.5 text-sm text-gray-500">
                  {applicant.submitted_at ? applicant.submitted_at.slice(0, 10) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 rounded-xl px-5 py-3 text-sm font-medium shadow-lg ${
            toast.ok ? "bg-gray-900 text-white" : "bg-red-500 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
