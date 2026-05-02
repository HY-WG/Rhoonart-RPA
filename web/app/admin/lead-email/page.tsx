"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const projects = [
  {
    id: 1,
    name: "여름밤의 세레나데",
    emails: [
      "channel1@example.com",
      "channel2@example.com",
      "channel3@example.com",
      "channel4@example.com",
    ],
  },
  {
    id: 2,
    name: "힙합 컴필레이션 Vol.2",
    emails: [
      "music.channel@example.com",
      "hiphop.lovers@example.com",
      "beats.official@example.com",
    ],
  },
];

export default function LeadEmailPage() {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({ 1: true });

  const toggle = (id: number) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">리드 채널 메일 발송</h1>

      <div className="space-y-3">
        {projects.map((project) => (
          <div key={project.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            {/* 헤더 */}
            <button
              onClick={() => toggle(project.id)}
              className="w-full flex items-center gap-2 px-5 py-4 hover:bg-gray-50 transition-colors text-left"
            >
              {expanded[project.id] ? (
                <ChevronDown className="w-4 h-4 text-gray-500 shrink-0" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
              )}
              <span className="font-semibold text-gray-800">{project.name}</span>
            </button>

            {/* 이메일 목록 */}
            {expanded[project.id] && (
              <>
                <div className="border-t border-gray-100">
                  {project.emails.map((email) => (
                    <div
                      key={email}
                      className="flex items-center justify-between px-5 py-3.5 border-b border-gray-50 last:border-0"
                    >
                      <span className="text-sm text-gray-600">{email}</span>
                      <button className="px-4 py-1.5 bg-teal-500 text-white text-sm rounded-lg hover:bg-teal-600 transition-colors">
                        발송
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex justify-end px-5 py-3.5 border-t border-gray-100">
                  <button className="px-5 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors">
                    일괄 전송
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
