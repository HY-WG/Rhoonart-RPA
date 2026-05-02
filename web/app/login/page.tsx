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
    setLoading(true); setError(null);
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!supabaseUrl || !supabaseKey) { setError("\ud658\uacbd\ubcc0\uc218 NEXT_PUBLIC_SUPABASE_URL \ub610\ub294 NEXT_PUBLIC_SUPABASE_ANON_KEY\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."); setLoading(false); return; }
    try {
      const supabase = createClient();
      const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;
      const { error } = await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo } });
      if (error) { setError(error.message); setLoading(false); }
    } catch (e) { setError(e instanceof Error ? e.message : "\uc54c \uc218 \uc5c6\ub294 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4."); setLoading(false); }
  };
  return <div className="min-h-screen flex items-center justify-center bg-slate-50"><div className="bg-white rounded-2xl shadow-lg p-10 w-full max-w-sm flex flex-col items-center gap-6"><div className="flex flex-col items-center gap-2"><div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center"><span className="text-white text-2xl font-bold">R</span></div><h1 className="text-xl font-bold text-slate-800">Rhoonart</h1><p className="text-sm text-slate-500">{"\uc5c5\ubb34 \uc790\ub3d9\ud654 \uad00\ub9ac \uc2dc\uc2a4\ud15c"}</p></div><hr className="w-full border-slate-100" />{error && <div className="w-full px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">{error}</div>}{process.env.NODE_ENV === "development" && <p className="text-xs text-slate-300 break-all text-center">{process.env.NEXT_PUBLIC_SUPABASE_URL ?? "SUPABASE_URL \ubbf8\uc124\uc815"}</p>}<button onClick={handleGoogleLogin} disabled={loading} className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50">{loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <span className="w-5 h-5 rounded-full border border-slate-300" />}{loading ? "\uc5f0\uacb0 \uc911..." : "Google \uacc4\uc815\uc73c\ub85c \ub85c\uadf8\uc778"}</button><p className="text-xs text-slate-400 text-center">{"Rhoonart \uc5c5\ubb34 \uacc4\uc815\uc73c\ub85c\ub9cc \ub85c\uadf8\uc778\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4."}</p></div></div>;
}

export default function LoginPage() { return <Suspense><LoginForm /></Suspense>; }
