import LeadDiscoveryResult from "./lead-discovery-result";

export default async function LeadDiscoveryResultPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <LeadDiscoveryResult runId={runId} />;
}
