"use server";

import { randomUUID } from "node:crypto";
import { redirect } from "next/navigation";
import { Pool } from "pg";
import { auth } from "../../auth";
import { issueApiToken } from "../../lib/api-token";
import { availableWorkspaceSlug } from "../../lib/onboarding";

const databaseUrl = process.env.DATABASE_URL?.replace("postgresql+asyncpg://", "postgresql://");
const pool = databaseUrl ? new Pool({ connectionString: databaseUrl }) : undefined;

export async function createWorkspace(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) redirect("/login?callbackUrl=/onboarding");
  if (!pool) throw new Error("DATABASE_URL não está configurada");
  const name = String(formData.get("company") ?? "").trim();
  const timezone = String(formData.get("timezone") ?? "America/Sao_Paulo");
  const agentName = String(formData.get("agent_name") ?? "").trim();
  const templateId = String(formData.get("template_id") ?? "receptionist");
  const voiceId = String(formData.get("voice_id") ?? "").trim();
  if (!name || !agentName) throw new Error("Empresa e agente são obrigatórios");
  const tenantId = randomUUID();
  const baseSlug = availableWorkspaceSlug(name, []);
  const existing = await pool.query<{ slug: string }>("SELECT slug FROM tenants WHERE slug LIKE $1", [`${baseSlug}%`]);
  const slug = availableWorkspaceSlug(name, existing.rows.map((row) => row.slug));
  const client = await pool.connect();
  let agentId = "";
  try {
    await client.query("BEGIN");
    await client.query("INSERT INTO tenants(id,slug,name,status,settings) VALUES($1,$2,$3,'trial',$4::jsonb)", [tenantId, slug, name, JSON.stringify({ timezone, locale: "pt-BR", retention_days: 90, recording_enabled: true })]);
    await client.query('INSERT INTO memberships(tenant_id,"user_id",role) VALUES($1,$2,\'owner\')', [tenantId, session.user.id]);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK"); throw error;
  } finally { client.release(); }
  try {
    const issued = await issueApiToken(session.user.id);
    if (!issued) throw new Error("Falha ao emitir token do workspace");
    const headers = { authorization: `Bearer ${issued.token}`, "x-tenant-id": tenantId, "content-type": "application/json" };
    const apiUrl = process.env.API_INTERNAL_URL ?? "http://api:8000";
    const created = await fetch(`${apiUrl}/v1/agents`, { method: "POST", headers, body: JSON.stringify({ name: agentName, template_id: templateId }) });
    if (!created.ok) throw new Error(`Falha ao criar agente: HTTP ${created.status}`);
    const agent = await created.json() as { id: string };
    agentId = agent.id;
    if (voiceId) {
      const configured = await fetch(`${apiUrl}/v1/agents/${agent.id}/draft`, { method: "PATCH", headers, body: JSON.stringify({ tts: { provider: "elevenlabs", model: "eleven_flash_v2_5", voice_id: voiceId } }) });
      if (!configured.ok) throw new Error(`Falha ao configurar voz: HTTP ${configured.status}`);
    }
  } catch (error) {
    await pool.query("DELETE FROM tenants WHERE id=$1", [tenantId]); throw error;
  }
  redirect(`/app/${slug}?onboarding=success&agent=${agentId}`);
}
