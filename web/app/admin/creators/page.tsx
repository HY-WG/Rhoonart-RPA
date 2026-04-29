import { createClient } from "@/lib/supabase/server";
import { Users, Mail, Youtube } from "lucide-react";

type Creator = {
  id: string;
  user_id: string;
  email: string;
  channel_name: string | null;
  channel_url: string | null;
  created_at: string;
};

async function getCreators(): Promise<Creator[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("user_roles")
    .select(`
      user_id,
      created_at,
      profiles:user_id (
        email,
        channel_name,
        channel_url
      )
    `)
    .eq("role", "creator")
    .order("created_at", { ascending: false });

  if (error || !data) return [];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return data.map((row: any) => ({
    id: row.user_id,
    user_id: row.user_id,
    email: row.profiles?.email ?? "-",
    channel_name: row.profiles?.channel_name ?? null,
    channel_url: row.profiles?.channel_url ?? null,
    created_at: row.created_at,
  }));
}

export default async function CreatorsPage() {
  const creators = await getCreators().catch(() => [] as Creator[]);

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <Users className="w-6 h-6 text-indigo-500" />
          크리에이터 목록
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          등록된 크리에이터 {creators.length}명
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {creators.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-400 gap-2">
            <Users className="w-8 h-8 opacity-30" />
            <p className="text-sm">등록된 크리에이터가 없습니다.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-5 py-3 text-slate-500 font-medium">이메일</th>
                <th className="text-left px-5 py-3 text-slate-500 font-medium">채널명</th>
                <th className="text-left px-5 py-3 text-slate-500 font-medium">가입일</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {creators.map((creator) => (
                <tr key={creator.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-xs font-bold shrink-0">
                        {creator.email[0]?.toUpperCase() ?? "C"}
                      </div>
                      <span className="text-slate-700">{creator.email}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-slate-500">
                    {creator.channel_name ?? (
                      <span className="text-slate-300">미등록</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-slate-400">
                    {new Date(creator.created_at).toLocaleDateString("ko-KR")}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex gap-1.5">
                      {creator.channel_url && (
                        <a
                          href={creator.channel_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                          title="YouTube 채널"
                        >
                          <Youtube className="w-4 h-4" />
                        </a>
                      )}
                      <a
                        href={`mailto:${creator.email}`}
                        className="p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 rounded transition-colors"
                        title="이메일 발송"
                      >
                        <Mail className="w-4 h-4" />
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
