"use client";

import { QueryClient } from "@tanstack/react-query";

let client: QueryClient | null = null;

export function getQueryClient() {
  if (!client) {
    client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 10_000,
          refetchOnWindowFocus: true,
          retry: 1,
        },
      },
    });
  }
  return client;
}
