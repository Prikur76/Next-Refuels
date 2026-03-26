"use client";

import { useQuery } from "@tanstack/react-query";

import { getMe } from "@/lib/api/endpoints";
import type { UserMeOut } from "@/lib/api/types";

export function useMeQuery(options?: { enabled?: boolean }) {
  return useQuery<UserMeOut, Error>({
    queryKey: ["auth", "me"],
    queryFn: () => getMe(),
    enabled: options?.enabled ?? true,
  });
}

