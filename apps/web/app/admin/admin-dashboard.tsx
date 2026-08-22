"use client";

import { useCallback, useEffect, useState } from "react";

type Tenant = {
  id: string;
  slug: string;
  name: string;
  status: string;
  plan_code?: string;
  agents_count: number;
  calls_count: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/voiceos/admin/${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error?.message ?? "Acesso administrativo negado");
  return body as T;
}

export default function AdminDashboard() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [tenantResult, metricResult] = await Promise.all([
        request<{ data: Tenant[] }>("tenants"),
        request<Record<string, number>>("metrics"),
      ]);
      setTenants(tenantResult.data);
      setMetrics(metricResult);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }, []);
  useEffect(() => void refresh(), [refresh]);

  async function updateTenant(id: string, data: Record<string, string>) {
    try {
      await request(`tenants/${id}`, { method: "PATCH", body: JSON.stringify(data) });
      await refresh();
      setNotice("Tenant atualizado e ação auditada.");
    } catch (error) {
      setNotice(String(error));
    }
  }

  return (
    <main style={{ maxWidth: 1200, margin: "40px auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>VoiceOS Platform Admin</h1>
      {notice && <p>{notice}</p>}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(5,minmax(120px,1fr))", gap: 12 }}>
        {Object.entries(metrics).map(([key, value]) => <article key={key} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 12 }}><small>{key}</small><h2>{Number(value).toFixed(key === "cost" ? 2 : 0)}</h2></article>)}
      </section>
      <h2>Tenants</h2>
      {tenants.map((tenant) => (
        <article key={tenant.id} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 12, alignItems: "center", padding: 16, borderBottom: "1px solid #ddd" }}>
          <span><strong>{tenant.name}</strong><br /><small>{tenant.slug} · {tenant.agents_count} agentes · {tenant.calls_count} chamadas</small></span>
          <select value={tenant.plan_code ?? "trial"} onChange={(event) => void updateTenant(tenant.id, { plan_code: event.target.value })}><option value="trial">Trial</option><option value="starter">Starter</option><option value="pro">Pro</option><option value="business">Business</option><option value="enterprise">Enterprise</option></select>
          <select value={tenant.status} onChange={(event) => void updateTenant(tenant.id, { status: event.target.value })}><option value="trial">Trial</option><option value="active">Ativo</option><option value="past_due">Past due</option><option value="suspended">Suspenso</option><option value="cancelled">Cancelado</option></select>
          <a href={`/app/${tenant.slug}`}>Abrir workspace</a>
        </article>
      ))}
    </main>
  );
}
