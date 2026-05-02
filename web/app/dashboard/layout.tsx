import TopHeader from "@/components/top-header";
import AdminSidebar from "@/components/admin-sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
