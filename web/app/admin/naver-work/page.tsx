"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

type Channel = { id: string; channel_name: string };

export default function NaverWorkPage() {
  const [workName, setWorkName] = useState("");
  const [workCode, setWorkCode] = useState("");
  const [contractChannel, setContractChannel] = useState("");
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // 승인된 채널 목록 로드
  useEffect(() => {
    const supabase = createClient();
    supabase
      .from("channel_approvals")
      .select("id, channel_name")
      .eq("status", "approved")
      .then(({ data }) => setChannels(data ?? []));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workName || !workCode) {
      setResult({ type: "error", msg: "작품 이름과 작품 코드는 필수입니다." });
      return;
    }
    setLoading(true);
    setResult(null);

    const supabase = createClient();
    const { error } = await supabase.from("works").insert({
      work_name: workName,
      work_code: workCode,
      contract_channel: contractChannel,
    });

    setLoading(false);
    if (error) {
      setResult({ type: "error", msg: `오류: ${error.message}` });
    } else {
      setResult({ type: "success", msg: "작품 정보가 성공적으로 등록되었습니다." });
      setWorkName("");
      setWorkCode("");
      setContractChannel("");
    }
  };

  return (
    <div className="p-8">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden max-w-2xl">
        <div className="px-8 py-6 border-b border-gray-100">
          <h1 className="text-2xl font-bold text-gray-900">네이버 작품 정보 추가</h1>
          <p className="text-sm text-gray-400 mt-1">Supabase works 테이블에 저장됩니다.</p>
        </div>

        <form onSubmit={handleSubmit} className="px-8 py-6 space-y-5">
          {/* 작품 이름 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">
              작품 이름 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={workName}
              onChange={(e) => setWorkName(e.target.value)}
              placeholder="작품 이름을 입력하세요"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent"
            />
          </div>

          {/* 작품 코드 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">
              작품 코드 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={workCode}
              onChange={(e) => setWorkCode(e.target.value)}
              placeholder="예) NVR-2026-001"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent"
            />
          </div>

          {/* 계약 채널 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">계약 채널</label>
            {channels.length > 0 ? (
              <select
                value={contractChannel}
                onChange={(e) => setContractChannel(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent"
              >
                <option value="">채널을 선택하세요</option>
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.channel_name}>
                    {ch.channel_name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={contractChannel}
                onChange={(e) => setContractChannel(e.target.value)}
                placeholder="계약 채널명을 입력하세요"
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent"
              />
            )}
          </div>

          {/* 결과 메시지 */}
          {result && (
            <div
              className={`px-4 py-3 rounded-lg text-sm font-medium ${
                result.type === "success"
                  ? "bg-teal-50 text-teal-700 border border-teal-200"
                  : "bg-red-50 text-red-600 border border-red-200"
              }`}
            >
              {result.type === "success" ? "✓ " : "✗ "}{result.msg}
            </div>
          )}

          {/* 버튼 */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-teal-500 text-white text-sm font-semibold rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "등록 중..." : "네이버 작품 정보 추가"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
