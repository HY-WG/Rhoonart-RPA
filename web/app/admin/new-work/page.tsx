"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { registerAdminVideo } from "@/lib/api";

export default function NewWorkPage() {
  const [title, setTitle] = useState("");
  const [holder, setHolder] = useState("");
  const mutation = useMutation({ mutationFn: registerAdminVideo });
  function submit(event: FormEvent) { event.preventDefault(); mutation.mutate({ title, rights_holder_name: holder, registered_by: "admin" }); }
  return <div className="max-w-2xl p-8"><h1 className="text-2xl font-bold text-slate-950">{"\uc2e0\uaddc \uc601\uc0c1 \ub4f1\ub85d"}</h1><p className="mt-1 text-sm text-slate-500">{"C-3 \uc601\uc0c1 \ub4f1\ub85d \ud750\ub984\uc73c\ub85c \uc5f0\uacb0\ub418\ub294 \uc785\ub825 \ud654\uba74\uc785\ub2c8\ub2e4."}</p><form onSubmit={submit} className="mt-6 rounded-lg border border-slate-200 bg-white p-6"><label className="block text-sm font-medium text-slate-700">{"\uc601\uc0c1 \uc81c\ubaa9"}<input value={title} onChange={(e) => setTitle(e.target.value)} required className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 outline-none focus:border-blue-500" /></label><label className="mt-4 block text-sm font-medium text-slate-700">{"\uad8c\ub9ac\uc0ac"}<input value={holder} onChange={(e) => setHolder(e.target.value)} required className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 outline-none focus:border-blue-500" /></label><button disabled={mutation.isPending} className="mt-6 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{"\ub4f1\ub85d\ud558\uae30"}</button>{mutation.data && <p className="mt-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{mutation.data.message} {"\uc694\uccad ID"}: {mutation.data.request_id}</p>}{mutation.isError && <p className="mt-4 text-sm text-red-600">{(mutation.error as Error).message}</p>}</form></div>;
}
