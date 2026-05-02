import TopHeader from "@/components/top-header";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <TopHeader />
      <main className="flex-1">{children}</main>
    </div>
  );
}
