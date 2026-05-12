"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Search, X } from "lucide-react";
import {
  createNaverContentCatalogItem,
  fetchNaverContentCatalog,
  updateNaverWorkReportEnabled,
} from "@/lib/api";
import type { NaverContentCatalogCreate, NaverContentCatalogItem } from "@/lib/types";

type DraftMap = Record<number, boolean>;

const EMPTY_FORM: NaverContentCatalogCreate = {
  content_name: "",
  identifier: "",
  rights_holder_name: "",
  status: "Active",
  naver_report_enabled: true,
};

function workKey(work: NaverContentCatalogItem) {
  return work.id ?? 0;
}

function isEnabled(work: NaverContentCatalogItem) {
  return Boolean(work.naver_report_enabled);
}

export default function NaverReportWorksPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<DraftMap>({});
  const [keyword, setKeyword] = useState("");
  const [holderFilter, setHolderFilter] = useState("all");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<NaverContentCatalogCreate>(EMPTY_FORM);

  const query = useQuery({
    queryKey: ["naver-content-catalog"],
    queryFn: fetchNaverContentCatalog,
    staleTime: 30_000,
  });

  useEffect(() => {
    const next: DraftMap = {};
    for (const work of query.data ?? []) {
      const id = workKey(work);
      if (id) next[id] = isEnabled(work);
    }
    setDraft(next);
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const works = query.data ?? [];
      const changed = works.filter((work) => {
        const id = workKey(work);
        return id && draft[id] !== isEnabled(work);
      });
      const results = [];
      for (const work of changed) {
        const id = workKey(work);
        results.push(await updateNaverWorkReportEnabled(id, draft[id]));
      }
      return results;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["naver-content-catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["metabase-report"] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createNaverContentCatalogItem({
        ...form,
        content_name: form.content_name.trim(),
        identifier: form.identifier.trim(),
        rights_holder_name: form.rights_holder_name.trim(),
        status: form.status?.trim() || "Active",
      }),
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      void queryClient.invalidateQueries({ queryKey: ["naver-content-catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["metabase-report"] });
    },
  });

  const works = query.data ?? [];
  const rightsHolders = useMemo(
    () =>
      Array.from(
        new Set(works.map((work) => work.rights_holder_name).filter(Boolean))
      ).sort((a, b) => a.localeCompare(b, "ko")),
    [works]
  );

  const filteredWorks = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return works
      .filter((work) =>
        holderFilter === "all" ? true : work.rights_holder_name === holderFilter
      )
      .filter((work) => {
        if (!normalizedKeyword) return true;
        return [
          work.content_name,
          work.rights_holder_name,
          work.identifier,
          work.status,
          work.active_flag,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalizedKeyword));
      })
      .sort((a, b) => {
        const enabledDiff =
          Number(draft[workKey(b)] ?? false) - Number(draft[workKey(a)] ?? false);
        if (enabledDiff) return enabledDiff;
        const holderDiff = a.rights_holder_name.localeCompare(b.rights_holder_name, "ko");
        if (holderDiff) return holderDiff;
        return a.content_name.localeCompare(b.content_name, "ko");
      });
  }, [draft, holderFilter, keyword, works]);

  const changedCount = works.filter((work) => {
    const id = workKey(work);
    return id && draft[id] !== isEnabled(work);
  }).length;
  const enabledCount = works.filter((work) => draft[workKey(work)]).length;
  const canCreate =
    form.content_name.trim() && form.identifier.trim() && form.rights_holder_name.trim();

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">
              Naver Works
            </p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900">
              보고 작품 관리
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              naver_works의 작품 등록과 보고 여부를 관리합니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowCreateForm((value) => !value)}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:border-blue-400 hover:text-blue-700"
            >
              {showCreateForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {showCreateForm ? "등록 닫기" : "신규 작품 등록"}
            </button>
            <button
              type="button"
              disabled={changedCount === 0 || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Save className="h-4 w-4" />
              {saveMutation.isPending ? "저장 중" : `저장${changedCount ? ` (${changedCount})` : ""}`}
            </button>
          </div>
        </div>

        {showCreateForm && (
          <section className="mt-6 rounded-lg border border-blue-200 bg-white p-5">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
              <label className="flex flex-col gap-1 lg:col-span-2">
                <span className="text-xs font-medium text-slate-500">작품명</span>
                <input
                  value={form.content_name}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, content_name: event.target.value }))
                  }
                  placeholder="예: SNL 코리아 리부트 시즌8"
                  className="h-9 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-slate-500">identifier</span>
                <input
                  value={form.identifier}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, identifier: event.target.value }))
                  }
                  placeholder="예: NIvxu"
                  className="h-9 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-slate-500">권리사</span>
                <input
                  value={form.rights_holder_name}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, rights_holder_name: event.target.value }))
                  }
                  list="rights-holder-options"
                  placeholder="예: 쿠팡플레이(콘텐츠마이닝)"
                  className="h-9 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                />
                <datalist id="rights-holder-options">
                  {rightsHolders.map((holder) => (
                    <option key={holder} value={holder} />
                  ))}
                </datalist>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-slate-500">상태</span>
                <input
                  value={form.status ?? "Active"}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, status: event.target.value }))
                  }
                  className="h-9 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={form.naver_report_enabled}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      naver_report_enabled: event.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-slate-300 text-blue-600"
                />
                등록 즉시 보고 대상으로 사용
              </label>
              <button
                type="button"
                disabled={!canCreate || createMutation.isPending}
                onClick={() => createMutation.mutate()}
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
              >
                <Plus className="h-4 w-4" />
                {createMutation.isPending ? "등록 중" : "작품 등록"}
              </button>
            </div>
            {createMutation.isError && (
              <p className="mt-3 text-sm text-red-600">
                등록 실패: {(createMutation.error as Error).message}
              </p>
            )}
          </section>
        )}

        <section className="mt-6 grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-500">전체 작품</p>
            <p className="mt-1 text-2xl font-bold text-slate-900">{works.length}</p>
          </div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-xs font-medium text-emerald-700">보고 활성</p>
            <p className="mt-1 text-2xl font-bold text-emerald-900">{enabledCount}</p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="text-xs font-medium text-amber-700">저장 대기</p>
            <p className="mt-1 text-2xl font-bold text-amber-900">{changedCount}</p>
          </div>
        </section>

        <section className="mt-5 rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap gap-3">
            <label className="relative min-w-72 flex-1">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="작품명, 권리사, identifier 검색"
                className="h-9 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm text-slate-800 outline-none focus:border-blue-500"
              />
            </label>
            <select
              value={holderFilter}
              onChange={(event) => setHolderFilter(event.target.value)}
              className="h-9 min-w-56 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 outline-none focus:border-blue-500"
            >
              <option value="all">전체 권리사</option>
              {rightsHolders.map((holder) => (
                <option key={holder} value={holder}>
                  {holder}
                </option>
              ))}
            </select>
          </div>
        </section>

        {saveMutation.isSuccess && (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
            보고 여부를 저장했습니다.
          </div>
        )}

        {saveMutation.isError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
            저장 실패: {(saveMutation.error as Error).message}
          </div>
        )}

        <section className="mt-5 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="w-28 px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  보고 여부
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  작품명
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  권리사
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  identifier
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  상태
                </th>
              </tr>
            </thead>
            <tbody>
              {query.isLoading && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-400">
                    작품 목록을 불러오는 중입니다.
                  </td>
                </tr>
              )}
              {query.isError && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-red-500">
                    오류: {(query.error as Error).message}
                  </td>
                </tr>
              )}
              {!query.isLoading && !query.isError && filteredWorks.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-400">
                    표시할 작품이 없습니다.
                  </td>
                </tr>
              )}
              {filteredWorks.map((work) => {
                const id = workKey(work);
                const checked = Boolean(draft[id]);
                const changed = id && draft[id] !== isEnabled(work);
                return (
                  <tr
                    key={id || `${work.rights_holder_name}-${work.content_name}`}
                    className={[
                      "border-b border-slate-100 transition-colors last:border-b-0",
                      checked ? "bg-emerald-50/50" : "bg-white",
                      changed ? "outline outline-1 -outline-offset-1 outline-amber-300" : "",
                    ].join(" ")}
                  >
                    <td className="px-4 py-3">
                      <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={!id}
                          onChange={(event) => {
                            if (!id) return;
                            setDraft((prev) => ({
                              ...prev,
                              [id]: event.target.checked,
                            }));
                          }}
                          className="h-4 w-4 rounded border-slate-300 text-blue-600"
                        />
                        {checked ? "보고" : "제외"}
                      </label>
                    </td>
                    <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                      {work.content_name || "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {work.rights_holder_name || "-"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">
                      {work.identifier || "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500">
                      {work.status || work.active_flag || "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
