const leads = [
  {
    id: "1",
    thumbnail: "https://images.unsplash.com/photo-1511192336575-5a79af67a629?w=120&h=80&fit=crop",
    title: "여름밤의 세레나데",
    appliedChannels: 3,
    status: "진행",
    action: "view",
  },
  {
    id: "2",
    thumbnail: "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=120&h=80&fit=crop",
    title: "힙합 컴필레이션 Vol.2",
    appliedChannels: 12,
    status: "미진행",
    action: "start",
  },
];

export default function LeadDiscoveryPage() {
  return (
    <div className="p-8">
      <div className="mb-1">
        <h1 className="text-2xl font-bold text-gray-900">리드 채널 발굴</h1>
        <p className="text-sm text-gray-400 mt-1">신규프로젝트</p>
      </div>

      <div className="mt-6 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">썸네일</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">작품이름</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">신청 채널</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">리드 발굴</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">관리</th>
            </tr>
          </thead>
          <tbody>
            {leads.map((lead) => (
              <tr key={lead.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-6 py-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={lead.thumbnail}
                    alt={lead.title}
                    className="w-24 h-16 object-cover rounded-lg"
                  />
                </td>
                <td className="px-6 py-4 text-sm font-medium text-gray-800">{lead.title}</td>
                <td className="px-6 py-4 text-sm">
                  <span className={lead.status === "미진행" ? "text-teal-500 font-medium" : "text-gray-600"}>
                    {lead.appliedChannels}개
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span
                    className={`px-3 py-1 text-sm rounded-full font-medium ${
                      lead.status === "진행"
                        ? "bg-teal-50 text-teal-600"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {lead.status}
                  </span>
                </td>
                <td className="px-6 py-4">
                  {lead.action === "view" ? (
                    <button className="text-sm text-teal-600 hover:text-teal-700 font-medium">
                      내역 보기
                    </button>
                  ) : (
                    <button className="px-4 py-2 bg-teal-500 text-white text-sm rounded-lg hover:bg-teal-600 transition-colors">
                      발굴 시작
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
