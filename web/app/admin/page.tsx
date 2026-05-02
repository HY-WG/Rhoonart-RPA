"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight } from "lucide-react";
import { fetchAdminOverview } from "@/lib/api";

export default function AdminPage() {
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: fetchAdminOverview });
  return <div className="p-8"><div className="mb-6"><h1 className="text-2xl font-bold text-slate-950">{"\uc5b4\ub4dc\ubbfc"}</h1><p className="mt-1 text-sm text-slate-500">{"\uc791\ud488, \ucc44\ub110, \ud30c\ud2b8\ub108 \ud611\uc5c5 \ud604\ud669\uc744 \uad00\ub9ac\ud569\ub2c8\ub2e4."}</p></div><section><div className="mb-3 flex items-center gap-2"><AlertCircle className="h-5 w-5 text-blue-700" /><h2 className="text-lg font-semibold text-slate-900">{"\ubbf8\uacb0 \uc0ac\ud56d"}</h2></div>{overview.isLoading && <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">{"\ud604\ud669\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."}</div>}{overview.isError && <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center text-sm text-red-700">{(overview.error as Error).message}</div>}<div className="grid gap-4 md:grid-cols-3">{overview.data?.pending.map((item) => <Link key={item.id} href={item.id === "rights-relief" ? "/admin/work-application" : item.id === "naver-report" ? "/admin/reports/naver" : "/admin/videos"} className="rounded-lg border border-slate-200 bg-white p-5 hover:border-blue-200 hover:shadow-sm"><div className="flex items-start justify-between gap-4"><h3 className="font-semibold text-slate-950">{item.title}</h3><ArrowRight className="h-4 w-4 text-slate-400" /></div><p className="mt-4 text-sm text-slate-500">{item.metric_label} : <span className="text-2xl font-bold text-slate-950">{item.count}</span></p></Link>)}</div></section></div>;
}
