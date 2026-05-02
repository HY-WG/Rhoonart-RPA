const applications = [
  {
    id: 1,
    workTitle: "여름밤의 세레나데",
    channelName: "H Y",
    status: "승인",
    applicationDate: "2026-04-28",
    processDate: "2026-04-29",
  },
  {
    id: 2,
    workTitle: "힙합 컴필레이션 Vol.2",
    channelName: "뮤직채널",
    status: "대기중",
    applicationDate: "2026-04-27",
    processDate: "-",
  },
  {
    id: 3,
    workTitle: "어쿠스틱 라이브",
    channelName: "엔터테인먼트",
    status: "거부",
    applicationDate: "2026-04-25",
    processDate: "2026-04-26",
  },
];

const statusStyle = (s: string) => {
  if (s === "승인") return "bg-teal-50 text-teal-600";
  if (s === "대기중") return "bg-yellow-50 text-yellow-600";
  return "bg-red-50 text-red-500";
};

export default function WorkApplicationPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">작품 사용 신청 진행상황</h1>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">작품명</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">채널명</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">상태</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">신청일</th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">처리일</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => (
              <tr key={app.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-6 py-4 text-sm text-teal-600 font-medium hover:underline cursor-pointer">
                  {app.workTitle}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">{app.channelName}</td>
                <td className="px-6 py-4">
                  <span className={`px-3 py-1 text-sm rounded-full font-medium ${statusStyle(app.status)}`}>
                    {app.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">{app.applicationDate}</td>
                <td className="px-6 py-4 text-sm text-gray-600">{app.processDate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
