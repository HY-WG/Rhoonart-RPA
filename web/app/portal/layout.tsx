import { redirect } from "next/navigation";
import { getUser } from "@/lib/auth";
import TopHeader from "@/components/top-header";

export default async function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getUser();
  if (!user) redirect("/login");

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <TopHeader />
      <main className="flex-1">{children}</main>
      <footer className="py-6 text-center text-sm text-gray-400 border-t border-gray-100 bg-white">
        (주) 루나트론 | 대표 권재이
      </footer>
    </div>
  );
}
