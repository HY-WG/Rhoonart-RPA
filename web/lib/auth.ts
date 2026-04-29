import { createClient } from "@/lib/supabase/server";

export type UserRole = "admin" | "creator";

/**
 * 현재 로그인 유저의 역할을 반환합니다.
 * user_roles 테이블 조회 → 없으면 null
 */
export async function getUserRole(): Promise<UserRole | null> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const { data } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();

  return (data?.role as UserRole) ?? null;
}

/**
 * 현재 세션 유저 정보를 반환합니다.
 */
export async function getUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}
