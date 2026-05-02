import Link from "next/link";

type Video = {
  id: string;
  thumbnail: string;
  title: string;
  approvalStatus: "신청" | "대기중" | "승인";
};

const CHANNEL_DATA: Record<string, { name: string; videos: Video[] }> = {
  hy: {
    name: "H Y",
    videos: [
      {
        id: "1",
        thumbnail:
          "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=160&h=100&fit=crop",
        title: "여름 밤의 감성 뮤직비디오",
        approvalStatus: "신청",
      },
      {
        id: "2",
        thumbnail:
          "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?w=160&h=100&fit=crop",
        title: "통합 콘서트 하이라이트",
        approvalStatus: "대기중",
      },
      {
        id: "3",
        thumbnail:
          "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=160&h=100&fit=crop",
        title: "어쿠스틱 라이브 세션",
        approvalStatus: "신청",
      },
    ],
  },
};

export default async function ChannelDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const channel = CHANNEL_DATA[id] ?? CHANNEL_DATA.hy;

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <Link
        href="/portal"
        className="inline-flex items-center gap-1 text-sm text-teal-600 hover:text-teal-700 mb-6"
      >
        채널 목록으로
      </Link>

      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">
          {channel.name} - 사용 가능 영상
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          총 {channel.videos.length}개의 영상
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">
                썸네일
              </th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">
                제목
              </th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">
                승인
              </th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">
                쿠폰 신청
              </th>
              <th className="px-6 py-3.5 text-left text-sm text-gray-500 font-medium">
                저작권 설명
              </th>
            </tr>
          </thead>
          <tbody>
            {channel.videos.map((video) => (
              <tr
                key={video.id}
                className="border-b border-gray-50 hover:bg-gray-50"
              >
                <td className="px-6 py-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={video.thumbnail}
                    alt={video.title}
                    className="w-28 h-16 object-cover rounded-lg"
                  />
                </td>
                <td className="px-6 py-4">
                  <span className="text-sm text-teal-600 font-medium cursor-pointer hover:underline">
                    {video.title}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <button
                    className={`px-4 py-1.5 text-sm rounded-lg border transition-colors ${
                      video.approvalStatus === "대기중"
                        ? "bg-yellow-50 text-yellow-600 border-yellow-200"
                        : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    {video.approvalStatus}
                  </button>
                </td>
                <td className="px-6 py-4">
                  <button className="px-4 py-1.5 text-sm bg-teal-500 text-white rounded-lg hover:bg-teal-600 transition-colors">
                    쿠폰 신청
                  </button>
                </td>
                <td className="px-6 py-4">
                  <button className="px-4 py-1.5 text-sm bg-white text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                    저작권 설명
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
