"use client";

import { QueryClient } from "@tanstack/react-query";

// ── 데이터 성격별 staleTime 상수 ─────────────────────────────────────────────
// 탭 전환 시 불필요한 API 재호출을 막기 위한 캐싱 전략
// 사용법: useQuery({ ..., ...CACHE.SEMI_STATIC })

/** 준정적 데이터: 채널 조회, 보고 스케줄, 카카오 크리에이터 (10분 캐시) */
export const CACHE_SEMI_STATIC = {
  staleTime: 10 * 60 * 1_000,      // 10분 — 탭 전환 시 재요청 없음
  gcTime: 30 * 60 * 1_000,         // 30분 메모리 보존
  refetchOnWindowFocus: false,
} as const;

/** 동적 데이터: 성과 보고, 리드 발굴 결과 (1분 캐시) */
export const CACHE_DYNAMIC = {
  staleTime: 60 * 1_000,            // 1분
  gcTime: 5 * 60 * 1_000,
  refetchOnWindowFocus: true,
} as const;

/** 검색 자동완성: 키워드 검색 결과 (30초 캐시) */
export const CACHE_SEARCH = {
  staleTime: 30 * 1_000,
  gcTime: 2 * 60 * 1_000,
  refetchOnWindowFocus: false,
} as const;

// ── QueryClient 싱글톤 ────────────────────────────────────────────────────────
let client: QueryClient | null = null;

export function getQueryClient() {
  if (!client) {
    client = new QueryClient({
      defaultOptions: {
        queries: {
          // 전역 기본값: 5분 캐시 + 포커스 시 재요청 비활성
          // 동적 데이터 페이지는 useQuery에서 개별 override
          staleTime: 5 * 60 * 1_000,
          gcTime: 30 * 60 * 1_000,
          refetchOnWindowFocus: false,
          retry: 1,
        },
      },
    });
  }
  return client;
}
