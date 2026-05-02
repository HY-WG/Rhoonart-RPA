import { redirect } from "next/navigation";
import { getUserRole } from "@/lib/auth";
import TopHeader from "@/components/top-header";
import AdminSidebar from "@/components/admin-sidebar";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const role = await getUserRole();
  if (role !== "admin") redirect("/login");

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <TopHeader />
      <div className="flex flex-1 min-h-0">
        <AdminSidebar />
        <main className="flex-1 min-w-0 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
