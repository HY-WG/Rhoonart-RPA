"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const projects = [
  { id: 1, name: "\uc0ac\ub791\uc758 \ubd88\uc2dc\ucc29 \ud558\uc774\ub77c\uc774\ud2b8", emails: ["channel1@example.com", "channel2@example.com", "channel3@example.com"] },
  { id: 2, name: "\ud0b9\ub354\ub79c\ub4dc \uba85\uc7a5\uba74 \ubaa8\uc74c", emails: ["music.channel@example.com", "beats.official@example.com"] },
];

export default function LeadEmailPage() {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({ 1: true });
  return <div className="p-8"><h1 className="text-2xl font-bold text-gray-900 mb-6">{"\ub9ac\ub4dc \ucc44\ub110 \uba54\uc77c \ubc1c\uc1a1"}</h1><div className="space-y-3">{projects.map((project) => <div key={project.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden"><button onClick={() => setExpanded((prev) => ({ ...prev, [project.id]: !prev[project.id] }))} className="w-full flex items-center gap-2 px-5 py-4 hover:bg-gray-50 text-left">{expanded[project.id] ? <ChevronDown className="w-4 h-4 text-gray-500 shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />}<span className="font-semibold text-gray-800">{project.name}</span></button>{expanded[project.id] && <><div className="border-t border-gray-100">{project.emails.map((email) => <div key={email} className="flex items-center justify-between px-5 py-3.5 border-b border-gray-50 last:border-0"><span className="text-sm text-gray-600">{email}</span><button className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">{"\ubc1c\uc1a1"}</button></div>)}</div><div className="flex justify-end px-5 py-3.5 border-t border-gray-100"><button className="px-5 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">{"\uc77c\uad04 \uc804\uc1a1"}</button></div></>}</div>)}</div></div>;
}
