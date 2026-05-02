"use client";

import { createClient } from "@/lib/supabase/client";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Loader2 } from "lucide-react";

function LoginForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const urlError = searchParams.get("error");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(urlError);

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError(null);

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    console.log("[Login] SUPABASE_URL:", supabaseUrl);
    console.log("[Login] ANON_KEY set:", !!supabaseKey);

    if (!supabaseUrl || !supabaseKey) {
      setError("환경변수 미설정: NEXT_PUBLIC_SUPABASE_URL 또는 NEXT_PUBLIC_SUPABASE_ANON_KEY가 없습니다.");
      setLoading(false);
      return;
    }

    try {
      const supabase = createClient();
      const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;
      console.log("[Login] redirectTo:", redirectTo);

      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });

      console.log("[Login] signInWithOAuth result:", { data, error });

      if (error) {
        setError(error.message);
        setLoading(false);
      }
      // 성공 시 브라우저가 Google 페이지로 redirect됨
    } catch (e) {
      console.error("[Login] catch error:", e);
      setError(e instanceof Error ? e.message : "알 수 없는 오류가 발생했습니다.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-2xl shadow-lg p-10 w-full max-w-sm flex flex-col items-center gap-6">
        {/* 로고 */}
        <div className="flex flex-col items-center gap-2">
          <div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center">
            <span className="text-white text-2xl font-bold">R</span>
          </div>
          <h1 className="text-xl font-bold text-slate-800">Rhoonart</h1>
          <p className="text-sm text-slate-500">업무 자동화 관리 시스템</p>
        </div>

        <hr className="w-full border-slate-100" />

        {/* 에러 메시지 */}
        {error && (
          <div className="w-full px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
            {error}
          </div>
        )}

        {/* Supabase URL 확인용 (개발 환경) */}
        {process.env.NODE_ENV === "development" && (
          <p className="text-xs text-slate-300 break-all text-center">
            {process.env.NEXT_PUBLIC_SUPABASE_URL ?? "⚠️ SUPABASE_URL 미설정"}
          </p>
        )}

        {/* Google 로그인 버튼 */}
        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <svg viewBox="0 0 24 24" className="w-5 h-5" aria-hidden="true">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
          )}
          {loading ? "연결 중..." : "Google 계정으로 로그인"}
        </button>

        <p className="text-xs text-slate-400 text-center">
          루나트 업무용 Google 계정으로만 로그인할 수 있습니다.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
