import Dashboard from "./dashboard";

export default async function Page({ params }: { params: Promise<{ tenantSlug: string }> }) {
  const { tenantSlug } = await params;
  return <Dashboard tenantSlug={tenantSlug} />;
}
