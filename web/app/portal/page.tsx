import Link from "next/link";

const channels = [
  {
    id: "hy",
    name: "H Y",
    avatar: "https://i.pravatar.cc/40?img=11",
    status: "승인",
    registeredAt: "2026-04-28",
    approvedAt: "2026-04-28",
  },
];

export default function PortalPage() {
  const approvedCount = channels.filter((c) => c.status === "승인").length;

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      {/* 헤더 */}
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">채널</h1>
        <span className="px-3 py-1 bg-teal-50 text-teal-600 text-sm font-medium rounded-full">
          승인됨 {approvedCount}개
        </span>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">채널</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">상태</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">등록일</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">승인일</th>
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => (
              <tr key={ch.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-6 py-4">
                  <Link
                    href={`/portal/channels/${ch.id}`}
                    className="flex items-center gap-3 hover:opacity-80"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={ch.avatar}
                      alt={ch.name}
                      className="w-9 h-9 rounded-full object-cover"
                    />
                    <span className="font-medium text-gray-800">{ch.name}</span>
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <span className="px-3 py-1 bg-teal-50 text-teal-600 text-sm rounded-full font-medium">
                    {ch.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">{ch.registeredAt}</td>
                <td className="px-6 py-4 text-sm text-gray-600">{ch.approvedAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
