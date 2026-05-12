"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  Check,
  CheckCircle2,
  FileText,
  Loader2,
  Minus,
  Plus,
  ShieldCheck,
  Sparkles,
  ToggleRight,
} from "lucide-react";
import {
  enrichWork,
  fetchNaverRightsHolders,
  searchWorks,
  type WorkEnrichResult,
  type WorkSearchResult,
} from "@/lib/api";
import { CACHE_SEARCH, CACHE_SEMI_STATIC } from "@/lib/query-client";
import type { NaverRightsHolder } from "@/lib/types";

const VIDEO_TYPES = ["드라마", "영화", "예능", "스케치", "애니메이션", "기타"];
const GENRES = ["로맨스", "스릴러", "액션", "코미디", "판타지", "역사", "SF", "공호", "드라마", "스케치", "기타"];
const COUNTRIES = ["한국", "미국", "일본", "중국", "기타"];
const PLATFORM_OPTIONS = ["YouTube", "네이버 클립", "카카오TV", "틱톡", "넷플릭스", "웨이브", "티빙", "쇼츠", "기타"];
const PLATFORM_EXPANDABLE_OPTIONS = ["유튜브", "네이버 클립", "카카오톡 숏폼"];
const ASSETS_OPTIONS = ["작품 로고", "자막 파일", "키비주얼"];

type AutoFilledKeys = Partial<Record<keyof WorkForm, boolean>>;

interface WorkForm {
  work_title: string;
  rights_holder_name: string;
  release_year: string;
  description: string;
  director: string;
  cast: string;
  genre: string;
  video_type: string;
  country: string;
  platforms: string[];
  platform_video_url: string;
  trailer_url: string;
  thumbnail_url: string;
  source_download_url: string;
  // 가이드라인
  source_dates: string[];
  source_date_notes: string[];
  upload_dates: string[];
  upload_date_notes: string[];
  work_guide: string;
  format_guide: string;
  platform_expandable: string[];
  assets_provided: string[];
  precheck_required: boolean;
}

const EMPTY: WorkForm = {
  work_title: "",
  rights_holder_name: "",
  release_year: "",
  description: "",
  director: "",
  cast: "",
  genre: "",
  video_type: "",
  country: "한국",
  platforms: [],
  platform_video_url: "",
  trailer_url: "",
  thumbnail_url: "",
  source_download_url: "",
  source_dates: [""],
  source_date_notes: [""],
  upload_dates: [""],
  upload_date_notes: [""],
  work_guide: "",
  format_guide: "",
  platform_expandable: [],
  assets_provided: [],
  precheck_required: false,
};

function AiBadge() {
  return (
    <span className="ml-1.5 inline-flex items-center gap-0.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold text-violet-700">
      <Sparkles className="h-2.5 w-2.5" />
      AI
    </span>
  );
}

function RightsHolderToggle({
  value,
  onChange,
}: {
  value: string;
  onChange: (name: string) => void;
}) {
  const { data, isLoading, isError, error } = useQuery<NaverRightsHolder[]>({
    queryKey: ["naver-rights-holders-all"],
    queryFn: fetchNaverRightsHolders,
    ...CACHE_SEMI_STATIC,
    staleTime: 24 * 60 * 60 * 1_000,
    gcTime: 7 * 24 * 60 * 60 * 1_000,
    refetchOnMount: false,
    select: (list) =>
      [...list]
        .filter((holder) => holder.rights_holder_name)
        .sort((a, b) => a.rights_holder_name.localeCompare(b.rights_holder_name, "ko")),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-slate-400">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        권리사 목록을 불러오는 중입니다.
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-xs text-red-500">
        권리사 목록 조회 실패: {(error as Error).message}
      </p>
    );
  }

  const holders = data ?? [];
  if (holders.length === 0) {
    return <p className="text-xs text-slate-400">등록된 권리사가 없습니다.</p>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {holders.map((holder) => {
        const selected = value === holder.rights_holder_name;
        return (
          <button
            key={holder.rights_holder_name}
            type="button"
            onClick={() => onChange(selected ? "" : holder.rights_holder_name)}
            className={[
              "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              selected
                ? "border-teal-500 bg-teal-500 text-white shadow-sm"
                : "border-slate-200 bg-white text-slate-600 hover:border-teal-300 hover:text-teal-700",
            ].join(" ")}
          >
            {selected && <Check className="h-3 w-3" />}
            {holder.rights_holder_name}
          </button>
        );
      })}
    </div>
  );
}

function WorkTitleSearch({
  value,
  onChange,
  onSelect,
}: {
  value: string;
  onChange: (value: string) => void;
  onSelect: (item: WorkSearchResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const [debouncedValue, setDebouncedValue] = useState(value);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedValue(value.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [value]);

  const { data } = useQuery({
    queryKey: ["works-search", debouncedValue],
    queryFn: () => searchWorks(debouncedValue),
    enabled: debouncedValue.length >= 2,
    ...CACHE_SEARCH,
    staleTime: 24 * 60 * 60 * 1_000,
    gcTime: 24 * 60 * 60 * 1_000,
  });

  const results = data?.items ?? [];

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <input
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => value.length >= 2 && setOpen(true)}
        placeholder="작품명 입력"
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
      />
      {open && value.length >= 2 && results.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          {results.map((item) => (
            <li
              key={`${item.source ?? "internal"}-${item.work_id}`}
              onMouseDown={() => {
                onSelect(item);
                setOpen(false);
              }}
              className="flex cursor-pointer items-center justify-between px-3 py-2.5 text-sm hover:bg-slate-50"
            >
              <span className="font-medium text-slate-800">
                {item.display_title ?? item.work_title}
              </span>
              <span className="text-xs text-slate-400">
                {item.rights_holder_name || item.source?.toUpperCase() || "외부"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DateRowList({
  label,
  help,
  icon: Icon,
  dates,
  notes,
  onChange,
  onNotesChange,
}: {
  label: string;
  help: string;
  icon: React.ElementType;
  dates: string[];
  notes: string[];
  onChange: (dates: string[]) => void;
  onNotesChange: (notes: string[]) => void;
}) {
  const addRow = () => {
    onChange([...dates, ""]);
    onNotesChange([...notes, ""]);
  };
  const removeRow = (index: number) => {
    onChange(dates.filter((_, i) => i !== index));
    onNotesChange(notes.filter((_, i) => i !== index));
  };
  const updateRow = (index: number, value: string) =>
    onChange(dates.map((d, i) => (i === index ? value : d)));
  const updateNote = (index: number, value: string) =>
    onNotesChange(dates.map((_, i) => (i === index ? value : notes[i] ?? "")));

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
          <Icon className="h-4 w-4" />
        </span>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-slate-950">{label}</label>
            <button
              type="button"
              onClick={addRow}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              <Plus className="h-3 w-3" />
              추가
            </button>
          </div>
          <p className="mt-1 text-xs text-slate-400">{help}</p>
        </div>
      </div>
      <div className="space-y-2">
        {dates.map((date, index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              type="date"
              value={date}
              onChange={(e) => updateRow(index, e.target.value)}
              className="h-9 w-40 rounded-lg border border-slate-200 px-3 text-sm text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-400"
            />
            <input
              type="text"
              value={notes[index] ?? ""}
              onChange={(e) => updateNote(index, e.target.value)}
              placeholder="메모"
              className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 px-3 text-sm text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-400"
            />
            {dates.length > 1 && (
              <button
                type="button"
                onClick={() => removeRow(index)}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-400 hover:border-red-200 hover:text-red-500"
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function NewWorkPage() {
  const [form, setForm] = useState<WorkForm>(EMPTY);
  const [autoFilled, setAutoFilled] = useState<AutoFilledKeys>({});
  const [selectedCandidate, setSelectedCandidate] = useState<WorkSearchResult | null>(null);
  const [enrichLog, setEnrichLog] = useState<string[]>([]);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const enrichMutation = useMutation({
    mutationFn: () =>
      enrichWork(form.work_title, {
        source: selectedCandidate?.source,
        external_id: selectedCandidate?.external_id,
      }),
    onSuccess: (data: WorkEnrichResult) => {
      const filled: AutoFilledKeys = {};
      setEnrichLog(data.debug_log ?? []);
      setForm((prev) => {
        const next = { ...prev };
        const fields: (keyof WorkEnrichResult)[] = [
          "video_type",
          "release_year",
          "description",
          "genre",
          "country",
          "cast",
          "director",
          "trailer_url",
          "thumbnail_url",
        ];
        for (const key of fields) {
          const val = data[key];
          if (val && typeof val === "string" && val.trim()) {
            (next as Record<string, unknown>)[key] = val.trim();
            filled[key as keyof WorkForm] = true;
          }
        }
        return next;
      });
      setAutoFilled(filled);
    },
  });

  const submitMutation = useMutation({
    mutationFn: async (payload: WorkForm) => {
      const RPA_BASE = (
        process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001/dashboard"
      ).replace(/\/dashboard$/, "");
      const token = process.env.NEXT_PUBLIC_RPA_TOKEN ?? "";
      const guideline = {
        source_provided_date: payload.source_dates.find(Boolean) ?? undefined,
        upload_available_date: payload.upload_dates.find(Boolean) ?? undefined,
        usage_notes: [
          payload.work_guide,
          payload.source_dates
            .map((date, index) => [date, payload.source_date_notes[index]].filter(Boolean).join(" - "))
            .filter(Boolean)
            .map((line) => `소스 제공일 메모: ${line}`)
            .join("\n"),
          payload.upload_dates
            .map((date, index) => [date, payload.upload_date_notes[index]].filter(Boolean).join(" - "))
            .filter(Boolean)
            .map((line) => `업로드 가능일 메모: ${line}`)
            .join("\n"),
        ].filter(Boolean).join("\n\n"),
        format_guide: payload.format_guide,
        other_platforms: payload.platform_expandable.join(", "),
        logo_subtitle_provided: payload.assets_provided.length > 0,
        review_required: payload.precheck_required,
      };
      const res = await fetch(`${RPA_BASE}/api/c3/trigger`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "X-RPA-Token": token } : {}),
        },
        body: JSON.stringify({ payload: { ...payload, guideline } }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      setResult({ ok: true, msg: `"${form.work_title}" 등록을 요청했습니다.` });
      setForm(EMPTY);
      setAutoFilled({});
    },
    onError: (error) => {
      setResult({ ok: false, msg: (error as Error).message });
    },
  });

  const setField =
    <K extends keyof WorkForm>(key: K) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setAutoFilled((prev) => ({ ...prev, [key]: false }));
      setForm((prev) => ({ ...prev, [key]: event.target.value as WorkForm[K] }));
    };

  const togglePlatform = (platform: string) =>
    setForm((prev) => ({
      ...prev,
      platforms: prev.platforms.includes(platform)
        ? prev.platforms.filter((item) => item !== platform)
        : [...prev.platforms, platform],
    }));

  const togglePlatformExpandable = (platform: string) =>
    setForm((prev) => ({
      ...prev,
      platform_expandable: prev.platform_expandable.includes(platform)
        ? prev.platform_expandable.filter((item) => item !== platform)
        : [...prev.platform_expandable, platform],
    }));

  const toggleAsset = (asset: string) =>
    setForm((prev) => ({
      ...prev,
      assets_provided: prev.assets_provided.includes(asset)
        ? prev.assets_provided.filter((item) => item !== asset)
        : [...prev.assets_provided, asset],
    }));

  const fieldClass = (key: keyof WorkForm) =>
    `rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 ${
      autoFilled[key]
        ? "border-violet-300 bg-violet-50/40 focus:ring-violet-400"
        : "border-slate-200 focus:ring-teal-400"
    }`;

  const Label = ({
    text,
    required,
    fieldKey,
  }: {
    text: string;
    required?: boolean;
    fieldKey?: keyof WorkForm;
  }) => (
    <label className="flex items-center text-xs font-medium text-slate-600">
      {text}
      {required && <span className="ml-0.5 text-red-400">*</span>}
      {fieldKey && autoFilled[fieldKey] && <AiBadge />}
    </label>
  );

  const aiFilledCount = Object.values(autoFilled).filter(Boolean).length;

  return (
    <div className="max-w-3xl p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">신규 영상 등록</h1>
        <p className="mt-1 text-sm text-slate-500">
          작품명으로 메타데이터를 자동완성하고 C-3 영상 등록 흐름으로 연결합니다.
        </p>
      </div>

      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          setResult(null);
          submitMutation.mutate(form);
        }}
        className="space-y-6"
      >
        {/* ── 기본 정보 ─────────────────────────────────────────── */}
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">기본 정보</h2>
          <div className="grid grid-cols-2 gap-x-6 gap-y-4">
            <div className="col-span-2 flex flex-col gap-1">
              <Label text="작품명" required />
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <WorkTitleSearch
                    value={form.work_title}
                    onChange={(value) => {
                      setAutoFilled({});
                      setSelectedCandidate(null);
                      setForm((prev) => ({ ...prev, work_title: value }));
                    }}
                    onSelect={(item) => {
                      setAutoFilled({});
                      setSelectedCandidate(item);
                      setForm((prev) => ({
                        ...prev,
                        work_title: item.work_title,
                        release_year: item.release_year || prev.release_year,
                        rights_holder_name: prev.rights_holder_name || item.rights_holder_name,
                      }));
                    }}
                  />
                </div>
                <button
                  type="button"
                  disabled={!form.work_title || enrichMutation.isPending}
                  onClick={() => {
                    setAutoFilled({});
                    enrichMutation.mutate();
                  }}
                  className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-violet-300 bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-700 transition-colors hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {enrichMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                  {enrichMutation.isPending ? "조회 중" : "정보 자동완성"}
                </button>
              </div>
              {enrichMutation.isError && (
                <p className="mt-1 text-xs text-red-500">
                  오류: {(enrichMutation.error as Error).message}
                </p>
              )}
              {enrichMutation.isSuccess && aiFilledCount > 0 && (
                <p className="mt-1 flex items-center gap-1 text-xs text-violet-600">
                  <Sparkles className="h-3 w-3" />
                  {aiFilledCount}개 필드를 자동완성했습니다. 저장 전 내용을 확인해주세요.
                </p>
              )}
              {selectedCandidate?.source && selectedCandidate.source !== "internal" && (
                <p className="mt-1 text-xs text-slate-500">
                  선택한 후보: {selectedCandidate.display_title ?? selectedCandidate.work_title} ·{" "}
                  {selectedCandidate.source.toUpperCase()}
                </p>
              )}
              {enrichLog.length > 0 && (
                <div className="mt-2 rounded-md bg-slate-50 px-3 py-2">
                  <p className="text-xs font-semibold text-slate-600">Fallback 로그</p>
                  <ul className="mt-1 space-y-0.5">
                    {enrichLog.map((line) => (
                      <li key={line} className="font-mono text-[11px] text-slate-500">
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {enrichMutation.isSuccess && aiFilledCount === 0 && (
                <p className="mt-1 text-xs text-slate-400">
                  연결된 데이터 소스에서 해당 작품 정보를 찾지 못했습니다.
                </p>
              )}
            </div>

            <div className="col-span-2 flex flex-col gap-1.5">
              <Label text="권리사" required />
              <RightsHolderToggle
                value={form.rights_holder_name}
                onChange={(name) => setForm((prev) => ({ ...prev, rights_holder_name: name }))}
              />
            </div>

            <div className="flex flex-col gap-1">
              <Label text="출시 연도" fieldKey="release_year" />
              <input
                type="number"
                min={1900}
                max={2100}
                value={form.release_year}
                onChange={setField("release_year")}
                placeholder="예: 2024"
                className={fieldClass("release_year")}
              />
            </div>

            <div className="flex flex-col gap-1">
              <Label text="영상 유형" fieldKey="video_type" />
              <select value={form.video_type} onChange={setField("video_type")} className={fieldClass("video_type")}>
                <option value="">선택</option>
                {VIDEO_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <Label text="장르" fieldKey="genre" />
              <select value={form.genre} onChange={setField("genre")} className={fieldClass("genre")}>
                <option value="">선택</option>
                {GENRES.map((genre) => (
                  <option key={genre} value={genre}>
                    {genre}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <Label text="국가" fieldKey="country" />
              <select value={form.country} onChange={setField("country")} className={fieldClass("country")}>
                {COUNTRIES.map((country) => (
                  <option key={country} value={country}>
                    {country}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <Label text="감독" fieldKey="director" />
              <input value={form.director} onChange={setField("director")} placeholder="감독명" className={fieldClass("director")} />
            </div>

            <div className="col-span-2 flex flex-col gap-1">
              <Label text="출연진" fieldKey="cast" />
              <input value={form.cast} onChange={setField("cast")} placeholder="쉼표로 구분" className={fieldClass("cast")} />
            </div>

            <div className="col-span-2 flex flex-col gap-1">
              <Label text="작품 설명" fieldKey="description" />
              <textarea
                rows={3}
                value={form.description}
                onChange={setField("description")}
                placeholder="간략한 작품 소개"
                className={`resize-none ${fieldClass("description")}`}
              />
            </div>
          </div>
        </section>

        {/* ── 배포 플랫폼 ───────────────────────────────────────── */}
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">배포 플랫폼</h2>
          <div className="flex flex-wrap gap-2">
            {PLATFORM_OPTIONS.map((platform) => (
              <button
                key={platform}
                type="button"
                onClick={() => togglePlatform(platform)}
                className={[
                  "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  form.platforms.includes(platform)
                    ? "border-teal-500 bg-teal-500 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-teal-300 hover:text-teal-600",
                ].join(" ")}
              >
                {platform}
              </button>
            ))}
          </div>
        </section>

        {/* ── 링크 정보 ─────────────────────────────────────────── */}
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">링크 정보</h2>
          <div className="space-y-4">
            {[
              { key: "platform_video_url" as keyof WorkForm, label: "플랫폼 영상 URL", placeholder: "https://..." },
              { key: "trailer_url" as keyof WorkForm, label: "트레일러 URL", placeholder: "https://youtube.com/...", aiKey: "trailer_url" as keyof WorkForm },
              { key: "thumbnail_url" as keyof WorkForm, label: "영화/드라마 썸네일 URL", placeholder: "https://image.tmdb.org/...", aiKey: "thumbnail_url" as keyof WorkForm },
              { key: "source_download_url" as keyof WorkForm, label: "소스 다운로드 URL", placeholder: "https://drive.google.com/..." },
            ].map(({ key, label, placeholder, aiKey }) => (
              <div key={key} className="flex flex-col gap-1">
                <label className="flex items-center text-xs font-medium text-slate-600">
                  {label}
                  {aiKey && autoFilled[aiKey] && <AiBadge />}
                </label>
                <input value={form[key] as string} onChange={setField(key)} placeholder={placeholder} className={fieldClass(key)} />
              </div>
            ))}
          </div>
        </section>

        {/* ── 사용 가이드라인 ───────────────────────────────────── */}
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-5 text-sm font-semibold text-slate-700">사용 가이드라인</h2>

          <div className="grid gap-6 xl:grid-cols-[1fr_300px]">
            {/* 메인 필드 */}
            <div className="space-y-4">
              {/* 작품 소스 제공일 */}
              <DateRowList
                label="작품 소스 제공일"
                help="권리사가 원천 소스를 전달하는 예정일입니다."
                icon={CalendarDays}
                dates={form.source_dates}
                notes={form.source_date_notes}
                onChange={(dates) => setForm((prev) => ({ ...prev, source_dates: dates }))}
                onNotesChange={(notes) => setForm((prev) => ({ ...prev, source_date_notes: notes }))}
              />

              {/* 영상 업로드 가능일 */}
              <DateRowList
                label="영상 업로드 가능일"
                help="제작 완료 후 크리에이터 채널 게시가 허용되는 일자입니다."
                icon={CalendarDays}
                dates={form.upload_dates}
                notes={form.upload_date_notes}
                onChange={(dates) => setForm((prev) => ({ ...prev, upload_dates: dates }))}
                onNotesChange={(notes) => setForm((prev) => ({ ...prev, upload_date_notes: notes }))}
              />

              {/* 작품 관련 가이드 */}
              <div className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="mb-3 flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                    <ShieldCheck className="h-4 w-4" />
                  </span>
                  <div>
                    <label className="text-sm font-semibold text-slate-950">작품 관련 가이드</label>
                    <p className="mt-1 text-xs text-slate-400">
                      저작권, 노출 수위, 사용 금지 구간 등 작품 활용 시 주의사항입니다.
                    </p>
                  </div>
                </div>
                <textarea
                  rows={4}
                  value={form.work_guide}
                  onChange={setField("work_guide")}
                  placeholder="예: 원본 영상의 주요 결말 장면은 단독 클립으로 사용하지 않습니다."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-400"
                />
              </div>

              {/* 영상 포맷 가이드 */}
              <div className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="mb-3 flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                    <FileText className="h-4 w-4" />
                  </span>
                  <div>
                    <label className="text-sm font-semibold text-slate-950">영상 포맷 가이드</label>
                    <p className="mt-1 text-xs text-slate-400">
                      필수 삽입 문구, 설명란 고지, 해시태그 기준입니다.
                    </p>
                  </div>
                </div>
                <textarea
                  rows={4}
                  value={form.format_guide}
                  onChange={setField("format_guide")}
                  placeholder="예: #작품명 #네이버클립 / 설명란에 권리사 제공 문구 삽입"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-400"
                />
              </div>
            </div>

            {/* 사이드바 */}
            <div className="space-y-4">
              {/* 플랫폼 확장성 */}
              <div className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <ToggleRight className="h-5 w-5 text-blue-600" />
                  <h3 className="text-sm font-semibold text-slate-950">플랫폼 확장성</h3>
                </div>
                <div className="space-y-2">
                  {PLATFORM_EXPANDABLE_OPTIONS.map((platform) => (
                    <label
                      key={platform}
                      className="flex cursor-pointer items-center justify-between rounded-lg border border-slate-100 px-3 py-2 hover:bg-slate-50"
                    >
                      <span className="text-sm text-slate-700">{platform}</span>
                      <input
                        type="checkbox"
                        checked={form.platform_expandable.includes(platform)}
                        onChange={() => togglePlatformExpandable(platform)}
                        className="h-4 w-4 accent-blue-600"
                      />
                    </label>
                  ))}
                </div>
              </div>

              {/* 제공 자산 */}
              <div className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="text-sm font-semibold text-slate-950">제공 자산</h3>
                <p className="mt-1 text-xs text-slate-400">작품 로고 및 자막 파일 제공 여부입니다.</p>
                <div className="mt-4 space-y-2">
                  {ASSETS_OPTIONS.map((asset) => (
                    <label key={asset} className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={form.assets_provided.includes(asset)}
                        onChange={() => toggleAsset(asset)}
                        className="h-4 w-4 accent-blue-600"
                      />
                      {asset}
                    </label>
                  ))}
                </div>
              </div>

              {/* 사전 검수 */}
              <div className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />
                  <div>
                    <h3 className="text-sm font-semibold text-slate-950">사전 검수</h3>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      업로드 전 최종 결과물 컨펌 절차가 필요한 경우 활성화합니다.
                    </p>
                  </div>
                </div>
                <label className="mt-4 flex cursor-pointer items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                  <span className="text-sm text-slate-700">권리사 최종 확인 필요</span>
                  <input
                    type="checkbox"
                    checked={form.precheck_required}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, precheck_required: e.target.checked }))
                    }
                    className="h-4 w-4 accent-emerald-600"
                  />
                </label>
              </div>
            </div>
          </div>
        </section>

        {/* ── 제출 ──────────────────────────────────────────────── */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={submitMutation.isPending || !form.work_title || !form.rights_holder_name}
            className="rounded-lg bg-teal-500 px-6 py-2.5 text-sm font-semibold text-white hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitMutation.isPending ? "등록 중" : "등록하기"}
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
