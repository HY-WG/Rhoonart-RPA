import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// 역할별 접근 가능 경로
const ADMIN_PATHS = ["/admin", "/dashboard"];
const CREATOR_PATHS = ["/portal"];
const PUBLIC_PATHS = ["/login", "/auth/callback"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 공개 경로는 통과
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // 정적 파일 / Next.js 내부 경로 통과
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname === "/"
  ) {
    return NextResponse.next();
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // 세션 갱신
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // 로그인 필요
  if (!user) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 역할 조회
  const { data: roleData } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();

  const role = roleData?.role as "admin" | "creator" | undefined;

  // admin 전용 경로 접근 시 역할 체크
  if (ADMIN_PATHS.some((p) => pathname.startsWith(p))) {
    if (role === "creator") {
      // creator는 portal로
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = "/portal";
      return NextResponse.redirect(redirectUrl);
    }
    // role이 없거나 admin이면 통과 (역할 미지정 유저도 dashboard 접근 허용)
  }

  // creator 전용 경로 접근 시 역할 체크
  if (CREATOR_PATHS.some((p) => pathname.startsWith(p))) {
    if (role !== "creator") {
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = role === "admin" ? "/admin" : "/dashboard";
      return NextResponse.redirect(redirectUrl);
    }
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
