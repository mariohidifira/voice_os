import Dashboard from "./dashboard";

export default async function Page({ params, searchParams }: { params: Promise<{ tenantSlug: string }>; searchParams: Promise<{ onboarding?: string; agent?: string }> }) {
  const { tenantSlug } = await params;
  const query = await searchParams;
  return <Dashboard tenantSlug={tenantSlug} initialTestAgentId={query.onboarding === "success" ? query.agent : undefined} />;
}
