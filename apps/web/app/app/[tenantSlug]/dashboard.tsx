"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import VoiceWidget from "./voice-widget";

type Item = Record<string, unknown> & { id: string; name?: string; status?: string };
type Call = Item & { channel?: string; duration_s?: number; summary?: string; started_at?: string; turns?: Array<{ id?: string; role: string; text: string; audio_offset_ms?: number }>; recordings?: Array<{ url?: string; storage_key?: string }> };
type Section = "overview" | "agents" | "calls" | "knowledge" | "tools" | "members" | "settings";

const sections: Array<[Section, string]> = [["overview", "Visão geral"], ["agents", "Agentes"], ["calls", "Chamadas"], ["knowledge", "Conhecimento"], ["tools", "Ferramentas"], ["members", "Membros"], ["settings", "Configurações"]];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/voiceos/${path}`, { ...init, headers: { "content-type": "application/json", ...init?.headers } });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data?.detail?.message ?? data?.detail?.details?.errors?.join(" · ") ?? data?.error ?? `HTTP ${response.status}`;
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
function Empty({ children }: { children: React.ReactNode }) { return <div className="empty">{children}</div>; }

export default function Dashboard({ tenantSlug }: { tenantSlug: string }) {
  const [section, setSection] = useState<Section>("overview");
  const [agents, setAgents] = useState<Item[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [knowledge, setKnowledge] = useState<Item[]>([]);
  const [tools, setTools] = useState<Item[]>([]);
  const [members, setMembers] = useState<Item[]>([]);
  const [apiKeys, setApiKeys] = useState<Item[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [widgetAgentId, setWidgetAgentId] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<Item | null>(null);
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [me, a, c, k, t, keys] = await Promise.all([
        api<{ tenant_id: string }>("me"),
        api<{ data: Item[] }>("agents"), api<{ data: Call[] }>("calls"),
        api<{ data: Item[] }>("knowledge-bases"), api<{ data: Item[] }>("tools"), api<{ data: Item[] }>("api-keys"),
      ]);
      const memberResult = await api<{ data: Item[] }>(`tenants/${me.tenant_id}/members`);
      setTenantId(me.tenant_id); setMembers(memberResult.data); setApiKeys(keys.data);
      setAgents(a.data); setCalls(c.data); setKnowledge(k.data); setTools(t.data); setNotice("");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Falha ao carregar dados"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const today = new Date().toISOString().slice(0, 10);
  const todayCalls = calls.filter((call) => String(call.started_at ?? "").startsWith(today));
  const minutes = Math.round(calls.reduce((sum, call) => sum + Number(call.duration_s ?? 0), 0) / 60);
  const active = calls.filter((call) => ["queued", "ringing", "in_progress"].includes(call.status ?? "")).length;
  const completed = calls.filter((call) => call.status === "completed").length;

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const name = String(form.get("name") ?? "").trim(); if (!name) return;
    try { const created = await api<Item>("agents", { method: "POST", body: JSON.stringify({ name }) }); event.currentTarget.reset(); await refresh(); await openAgent(created.id); setNotice("Agente criado. Configure o rascunho antes de publicar."); }
    catch (error) { setNotice(String(error)); }
  }
  async function openAgent(id: string) { const detail = await api<Item>(`agents/${id}`); setSelectedAgent(detail); setSection("agents"); }
  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedAgent) return; const form = new FormData(event.currentTarget);
    const body = { system_prompt: String(form.get("system_prompt")), greeting: String(form.get("greeting")), language: String(form.get("language")), tts: { provider: "elevenlabs", model: "eleven_flash_v2_5", voice_id: String(form.get("voice_id")) }, turn_config: { allow_interruptions: form.get("allow_interruptions") === "on" }, behavior: { max_call_duration_s: Number(form.get("max_duration")), silence_timeout_s: Number(form.get("silence_timeout")) }, knowledge_base_id: form.get("knowledge_base_id") || null, rag: { enabled: Boolean(form.get("knowledge_base_id")) } };
    try { await api(`agents/${selectedAgent.id}/draft`, { method: "PATCH", body: JSON.stringify(body) }); await openAgent(selectedAgent.id); setNotice("Rascunho salvo."); } catch (error) { setNotice(String(error)); }
  }
  async function publishAgent() { if (!selectedAgent) return; try { await api(`agents/${selectedAgent.id}/publish`, { method: "POST", body: "{}" }); await refresh(); await openAgent(selectedAgent.id); setNotice("Versão publicada."); } catch (error) { setNotice(String(error)); } }
  function testAgent() { if (selectedAgent) setWidgetAgentId(selectedAgent.id); }
  async function openCall(id: string) { const detail = await api<Call>(`calls/${id}`); setSelectedCall(detail); setSection("calls"); }
  async function createKnowledge(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api("knowledge-bases", { method: "POST", body: JSON.stringify({ name: form.get("name") }) }); event.currentTarget.reset(); await refresh(); setNotice("Base criada."); } catch (error) { setNotice(String(error)); } }
  async function createTool(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api("tools", { method: "POST", body: JSON.stringify({ name: form.get("name"), description: form.get("description"), type: "webhook", parameters_schema: { type: "object", properties: {} }, webhook: { url: form.get("url"), method: "POST", timeout_ms: 5000 } }) }); event.currentTarget.reset(); await refresh(); setNotice("Ferramenta criada; execute o teste antes de publicar um agente que a use."); } catch (error) { setNotice(String(error)); } }
  async function inviteMember(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api(`tenants/${tenantId}/members`, { method: "POST", body: JSON.stringify({ email: form.get("email"), role: form.get("role") }) }); event.currentTarget.reset(); await refresh(); setNotice("Membro adicionado ao workspace."); } catch (error) { setNotice(String(error)); } }
  async function createApiKey(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); const origin = String(form.get("origin") ?? "").trim(); try { const result = await api<Item & { key: string }>("api-keys", { method: "POST", body: JSON.stringify({ name: form.get("name"), scope: form.get("scope"), allowed_origins: origin ? [origin] : [] }) }); event.currentTarget.reset(); await refresh(); setNotice(`Copie agora; esta chave não será mostrada novamente: ${result.key}`); } catch (error) { setNotice(String(error)); } }

  const draft = (selectedAgent?.draft ?? {}) as Record<string, unknown>;
  const stats = useMemo(() => [["Chamadas hoje", todayCalls.length], ["Minutos", minutes], ["Concluídas", completed], ["Ao vivo", active]], [todayCalls.length, minutes, completed, active]);

  return <div className="shell">
    <aside className="side"><div className="brand">Voice<span>OS</span></div><div className="tenant">Workspace<br/><strong>{tenantSlug}</strong></div><nav>{sections.map(([id, label]) => <button key={id} className={section === id ? "active" : ""} onClick={() => setSection(id)}>{label}</button>)}</nav></aside>
    <main><header className="top"><div><div className="eyebrow">tenant / {tenantSlug}</div><h1>{sections.find(([id]) => id === section)?.[1]}</h1></div><div className="topActions"><button className="secondary" onClick={() => void refresh()}>Atualizar</button><button onClick={() => setSection("agents")}>Novo agente</button></div></header>
      {notice && <div className="notice" role="status"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      {widgetAgentId && <VoiceWidget
        agentId={widgetAgentId}
        onNotice={setNotice}
        onClose={() => { setWidgetAgentId(null); void refresh(); }}
      />}
      {loading ? <div className="loading">Carregando operação…</div> : <>
        {section === "overview" && <><section className="stats">{stats.map(([label, value]) => <article className="card" key={label}><span className="muted">{label}</span><strong className="value">{value}</strong></article>)}</section><section className="split"><article className="card"><h2>Agentes</h2>{agents.slice(0, 5).map((agent) => <button className="row" key={agent.id} onClick={() => void openAgent(agent.id)}><span><strong>{agent.name}</strong><small>{agent.status}</small></span><b>→</b></button>)}{!agents.length && <Empty>Crie seu primeiro agente para iniciar.</Empty>}</article><article className="card"><h2>Chamadas recentes</h2>{calls.slice(0, 6).map((call) => <button className="row" key={call.id} onClick={() => void openCall(call.id)}><span><strong>{call.channel ?? "web"} · {call.status}</strong><small>{call.summary ?? new Date(call.started_at ?? Date.now()).toLocaleString("pt-BR")}</small></span><b>→</b></button>)}{!calls.length && <Empty>Nenhuma chamada registrada.</Empty>}</article></section></>}
        {section === "agents" && <section className="workspace"><aside className="list card"><h2>Agentes</h2><form className="inline" onSubmit={createAgent}><input name="name" placeholder="Nome do agente" required/><button>+</button></form>{agents.map((agent) => <button className={`row ${selectedAgent?.id === agent.id ? "selected" : ""}`} key={agent.id} onClick={() => void openAgent(agent.id)}><span><strong>{agent.name}</strong><small>{agent.status}</small></span></button>)}</aside><article className="card editor">{selectedAgent ? <><div className="editorHead"><div><div className="eyebrow">editor do agente</div><h2>{selectedAgent.name}</h2></div><div><button className="secondary" onClick={() => void testAgent()}>Testar</button><button onClick={() => void publishAgent()}>Publicar</button></div></div><div className="tabs"><span>Prompt</span><span>Voz</span><span>Conversa</span><span>Conhecimento</span><span>Tools</span><span>Avançado</span></div><form className="formGrid" onSubmit={saveAgent}><Field label="Prompt do sistema"><textarea name="system_prompt" defaultValue={String(draft.system_prompt ?? "")} rows={8}/></Field><Field label="Saudação"><textarea name="greeting" defaultValue={String(draft.greeting ?? "")} rows={3}/></Field><div className="two"><Field label="Idioma"><input name="language" defaultValue={String(draft.language ?? "pt-BR")}/></Field><Field label="Voice ID"><input name="voice_id" defaultValue={String((draft.tts as Record<string, unknown> | undefined)?.voice_id ?? "")}/></Field></div><div className="two"><Field label="Duração máxima (s)"><input name="max_duration" type="number" min="30" defaultValue={String((draft.behavior as Record<string, unknown> | undefined)?.max_call_duration_s ?? 900)}/></Field><Field label="Silêncio (s)"><input name="silence_timeout" type="number" min="5" defaultValue={String((draft.behavior as Record<string, unknown> | undefined)?.silence_timeout_s ?? 20)}/></Field></div><Field label="Base de conhecimento"><select name="knowledge_base_id" defaultValue={String(draft.knowledge_base_id ?? "")}><option value="">Sem base</option>{knowledge.map((kb) => <option value={kb.id} key={kb.id}>{kb.name}</option>)}</select></Field><label className="check"><input type="checkbox" name="allow_interruptions" defaultChecked={(draft.turn_config as Record<string, unknown> | undefined)?.allow_interruptions !== false}/> Permitir interrupções (barge-in)</label><button className="save">Salvar rascunho</button></form></> : <Empty>Selecione um agente ou crie um novo.</Empty>}</article></section>}
        {section === "calls" && <section className="workspace"><aside className="list card"><h2>Chamadas</h2>{calls.map((call) => <button className={`row ${selectedCall?.id === call.id ? "selected" : ""}`} key={call.id} onClick={() => void openCall(call.id)}><span><strong>{call.status} · {call.channel}</strong><small>{call.duration_s ?? 0}s · {call.summary ?? "Sem resumo"}</small></span></button>)}</aside><article className="card editor">{selectedCall ? <><div className="eyebrow">detalhe da chamada</div><h2>{selectedCall.summary ?? selectedCall.id}</h2><div className="callMeta"><span>Status <b>{selectedCall.status}</b></span><span>Duração <b>{selectedCall.duration_s ?? 0}s</b></span><span>Canal <b>{selectedCall.channel}</b></span></div>{selectedCall.recordings?.[0] && <audio controls src={selectedCall.recordings[0].url ?? `/recordings/${selectedCall.recordings[0].storage_key}`} />}<div className="transcript">{selectedCall.turns?.map((turn, index) => <div className={`turn ${turn.role}`} key={turn.id ?? index}><b>{turn.role === "user" ? "Pessoa" : "Agente"}</b><span>{turn.text}</span><small>{Math.round((turn.audio_offset_ms ?? 0) / 1000)}s</small></div>)}{!selectedCall.turns?.length && <Empty>A transcrição aparecerá aqui durante a chamada.</Empty>}</div></> : <Empty>Selecione uma chamada para ver áudio e transcrição sincronizada.</Empty>}</article></section>}
        {section === "knowledge" && <section className="split"><article className="card"><h2>Bases de conhecimento</h2><form className="inline" onSubmit={createKnowledge}><input name="name" placeholder="Nome da base" required/><button>Criar</button></form>{knowledge.map((kb) => <div className="row static" key={kb.id}><span><strong>{kb.name}</strong><small>{String(kb.embedding_model ?? "text-embedding-3-small")}</small></span><span className="pill">{String(kb.status ?? "ativa")}</span></div>)}</article><article className="card"><h2>Ingestão</h2><p className="muted">Selecione uma base e envie PDF, DOCX, HTML, URL ou texto. O pipeline extrai, divide, gera embeddings e disponibiliza a busca vetorial.</p><Empty>Crie ou selecione uma base para adicionar documentos.</Empty></article></section>}
        {section === "tools" && <section className="split"><article className="card"><h2>Ferramentas</h2>{tools.map((tool) => <div className="row static" key={tool.id}><span><strong>{tool.name}</strong><small>{String(tool.description ?? tool.type)}</small></span><span className={`pill ${tool.last_test_ok_at ? "ok" : ""}`}>{tool.last_test_ok_at ? "testada" : "pendente"}</span></div>)}</article><article className="card"><h2>Novo webhook</h2><form className="formGrid" onSubmit={createTool}><Field label="Nome snake_case"><input name="name" required pattern="[a-z0-9_]+"/></Field><Field label="Descrição"><input name="description" required maxLength={300}/></Field><Field label="URL HTTPS"><input name="url" type="url" required/></Field><button>Criar ferramenta</button></form></article></section>}
        {section === "members" && <section className="split"><article className="card"><h2>Membros</h2>{members.map((member) => <div className="row static" key={member.id}><span><strong>{String(member.name ?? member.email)}</strong><small>{String(member.email)}</small></span><span className="pill ok">{String(member.role)}</span></div>)}{!members.length && <Empty>Nenhum membro listado.</Empty>}</article><article className="card"><h2>Adicionar membro</h2><form className="formGrid" onSubmit={inviteMember}><Field label="E-mail"><input name="email" type="email" required/></Field><Field label="Papel"><select name="role"><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="developer">Developer</option><option value="admin">Admin</option></select></Field><button>Adicionar</button></form></article></section>}
        {section === "settings" && <section className="split"><article className="card"><h2>Integrações</h2><p>Google Calendar e Gmail</p><button className="secondary" onClick={async () => { try { const result = await api<{ url: string }>("integrations/google/connect"); location.href = result.url; } catch (error) { setNotice(String(error)); } }}>Conectar Google</button><h2>Chaves existentes</h2>{apiKeys.map((key) => <div className="row static" key={key.id}><span><strong>{key.name}</strong><small>{String(key.prefix)}… · {String(key.scope)}</small></span><span className={`pill ${key.revoked_at ? "" : "ok"}`}>{key.revoked_at ? "revogada" : "ativa"}</span></div>)}</article><article className="card"><h2>Nova API key</h2><p className="muted">A chave completa é exibida somente uma vez; apenas SHA-256 é armazenado.</p><form className="formGrid" onSubmit={createApiKey}><Field label="Nome"><input name="name" required/></Field><Field label="Escopo"><select name="scope"><option value="secret">Secret</option><option value="public">Public/widget</option></select></Field><Field label="Origem permitida (obrigatória para public)"><input name="origin" type="url" placeholder="https://cliente.com"/></Field><button>Criar chave</button></form></article></section>}
      </>}
    </main>
  </div>;
}
