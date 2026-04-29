import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/dashboard";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      // 역할에 따라 적절한 경로로 redirect
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (user) {
        const { data: roleData } = await supabase
          .from("user_roles")
          .select("role")
          .eq("user_id", user.id)
          .single();

        const role = roleData?.role as "admin" | "creator" | undefined;

        if (role === "creator") {
          return NextResponse.redirect(`${origin}/portal`);
        }
        // admin 또는 역할 미지정 → next 파라미터 경로로
        return NextResponse.redirect(`${origin}${next}`);
      }
    }
  }

  // 오류 발생 시 login으로 돌아감
  return NextResponse.redirect(`${origin}/login?error=auth`);
}
