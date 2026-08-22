"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import VoiceWidget from "./voice-widget";

type Item = Record<string, unknown> & {
  id: string;
  name?: string;
  status?: string;
};
type Call = Item & {
  channel?: string;
  duration_s?: number;
  summary?: string;
  started_at?: string;
  turns?: Array<{
    id?: string;
    role: string;
    text: string;
    audio_offset_ms?: number;
  }>;
  recording?: { url?: string; storage_key?: string };
  recordings?: Array<{ url?: string; storage_key?: string }>;
  tool_calls?: Array<Record<string, unknown>>;
  events?: Array<Record<string, unknown>>;
  latency?: Record<string, unknown>;
  cost?: Record<string, unknown>;
  variables?: Record<string, unknown>;
  outcome?: Record<string, unknown>;
};
type Document = Item & {
  source_type?: string;
  source_uri?: string;
  chunk_count?: number;
  error?: string;
};
type AgentTemplate = Item & {
  description?: string;
  suggested_tools?: string[];
};
type Section =
  | "overview"
  | "agents"
  | "calls"
  | "knowledge"
  | "tools"
  | "members"
  | "settings";
type AgentTab =
  | "prompt"
  | "voice"
  | "conversation"
  | "knowledge"
  | "tools"
  | "advanced";

const agentTabs: Array<[AgentTab, string]> = [
  ["prompt", "Prompt"],
  ["voice", "Voz"],
  ["conversation", "Conversa"],
  ["knowledge", "Conhecimento"],
  ["tools", "Tools"],
  ["advanced", "Avançado"],
];

const sections: Array<[Section, string]> = [
  ["overview", "Visão geral"],
  ["agents", "Agentes"],
  ["calls", "Chamadas"],
  ["knowledge", "Conhecimento"],
  ["tools", "Ferramentas"],
  ["members", "Membros"],
  ["settings", "Configurações"],
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/voiceos/${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail =
      data?.detail?.message ??
      data?.detail?.details?.errors?.join(" · ") ??
      data?.error ??
      `HTTP ${response.status}`;
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}
function CallEvidence({ call }: { call: Call }) {
  const recording = call.recording ?? call.recordings?.[0];
  const recordingUrl =
    recording?.url ??
    (recording?.storage_key ? `/recordings/${recording.storage_key}` : "");
  return (
    <section className="callEvidence card">
      <h2>Operação e métricas</h2>
      <div className="metricGrid">
        <span>
          Custo <b>USD {Number(call.cost?.total_usd ?? 0).toFixed(4)}</b>
        </span>
        <span>
          TTFB p50 <b>{String(call.latency?.ttfb_p50_ms ?? "—")} ms</b>
        </span>
        <span>
          TTFB p95 <b>{String(call.latency?.ttfb_p95_ms ?? "—")} ms</b>
        </span>
        <span>
          Barge-in p95 <b>{String(call.latency?.barge_in_p95_ms ?? "—")} ms</b>
        </span>
      </div>
      {recordingUrl && (
        <>
          <audio controls src={recordingUrl} />
          <p>
            <a href={recordingUrl} download>
              Baixar gravação
            </a>
          </p>
        </>
      )}
      <div className="two">
        <div>
          <h3>Tools chamadas</h3>
          {call.tool_calls?.map((tool, index) => (
            <details key={String(tool.id ?? index)}>
              <summary>
                {String(tool.name)} · {String(tool.status)} ·{" "}
                {String(tool.duration_ms ?? 0)} ms
              </summary>
              <pre>
                {JSON.stringify(
                  { arguments: tool.arguments, result: tool.result },
                  null,
                  2,
                )}
              </pre>
            </details>
          ))}
          {!call.tool_calls?.length && <small>Nenhuma tool chamada.</small>}
        </div>
        <div>
          <h3>Eventos</h3>
          {call.events?.map((event, index) => (
            <div className="eventRow" key={String(event.id ?? index)}>
              <b>{String(event.type)}</b>
              <small>{String(event.at ?? "")}</small>
            </div>
          ))}
          {!call.events?.length && <small>Nenhum evento adicional.</small>}
        </div>
      </div>
      <h3>Resultado e variáveis</h3>
      <pre>
        {JSON.stringify(
          { outcome: call.outcome ?? {}, variables: call.variables ?? {} },
          null,
          2,
        )}
      </pre>
    </section>
  );
}
function AgentAdvancedPanel({
  agent,
  draft,
  onSave,
  onStatus,
  onDelete,
}: {
  agent: Item;
  draft: Record<string, unknown>;
  onSave: (patch: Record<string, unknown>) => Promise<void>;
  onStatus: (status: string) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const llm = (draft.llm ?? {}) as Record<string, unknown>;
  const stt = (draft.stt ?? {}) as Record<string, unknown>;
  const tts = (draft.tts ?? {}) as Record<string, unknown>;
  const turn = (draft.turn_config ?? {}) as Record<string, unknown>;
  const behavior = (draft.behavior ?? {}) as Record<string, unknown>;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    let variables: Record<string, unknown>;
    try {
      variables = JSON.parse(String(form.get("variables") || "{}")) as Record<
        string,
        unknown
      >;
    } catch {
      throw new Error("Variáveis devem ser um objeto JSON válido.");
    }
    const preset = String(form.get("turn_preset"));
    const presetValues =
      preset === "fast"
        ? [0.35, 2]
        : preset === "patient"
          ? [0.8, 4]
          : [0.5, 3];
    await onSave({
      llm: {
        ...llm,
        provider: "anthropic",
        model: form.get("llm_model"),
        temperature: Number(form.get("temperature")),
        max_tokens: Number(form.get("max_tokens")),
      },
      stt: {
        ...stt,
        provider: "deepgram",
        model: "nova-3",
        keywords: String(form.get("keywords") || "")
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      },
      tts: {
        ...tts,
        provider: "elevenlabs",
        model: "eleven_flash_v2_5",
        voice_id: form.get("voice_id"),
        speed: Number(form.get("speed")),
        stability: Number(form.get("stability")),
      },
      turn_config: {
        ...turn,
        min_endpointing_delay: presetValues[0],
        max_endpointing_delay: presetValues[1],
        min_interruption_words: Number(form.get("min_interruption_words")),
        ignore_backchannels: String(form.get("backchannels") || "")
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      },
      behavior: {
        ...behavior,
        filler_enabled: form.get("filler_enabled") === "on",
        filler_phrases: String(form.get("filler_phrases") || "")
          .split("|")
          .map((value) => value.trim())
          .filter(Boolean),
        transfer_number: String(form.get("transfer_number") || "") || null,
      },
      variables,
    });
  }
  return (
    <section className="agentAdvanced card">
      <div className="editorHead">
        <div>
          <div className="eyebrow">configuração completa</div>
          <h2>Voz, conversa e avançado</h2>
        </div>
        <div>
          <button
            className="secondary"
            onClick={() =>
              void onStatus(agent.status === "paused" ? "active" : "paused")
            }
          >
            {agent.status === "paused" ? "Reativar" : "Pausar"}
          </button>
          <button className="danger" onClick={() => void onDelete()}>
            Excluir
          </button>
        </div>
      </div>
      <form className="formGrid" onSubmit={submit}>
        <div className="two">
          <Field label="Modelo LLM">
            <input
              name="llm_model"
              defaultValue={String(llm.model ?? "claude-sonnet-4-6")}
            />
          </Field>
          <Field label="Máximo de tokens">
            <input
              name="max_tokens"
              type="number"
              min="32"
              max="2000"
              defaultValue={String(llm.max_tokens ?? 350)}
            />
          </Field>
        </div>
        <Field label="Temperatura">
          <input
            name="temperature"
            type="number"
            min="0"
            max="1"
            step="0.1"
            defaultValue={String(llm.temperature ?? 0.3)}
          />
        </Field>
        <div className="two">
          <Field label="Voice ID">
            <input name="voice_id" defaultValue={String(tts.voice_id ?? "")} />
          </Field>
          <Field label="Velocidade">
            <input
              name="speed"
              type="number"
              min="0.5"
              max="2"
              step="0.05"
              defaultValue={String(tts.speed ?? 1)}
            />
          </Field>
        </div>
        <Field label="Estabilidade da voz">
          <input
            name="stability"
            type="number"
            min="0"
            max="1"
            step="0.05"
            defaultValue={String(tts.stability ?? 0.5)}
          />
        </Field>
        <div className="two">
          <Field label="Preset de turno">
            <select name="turn_preset" defaultValue="balanced">
              <option value="fast">Rápido</option>
              <option value="balanced">Equilibrado</option>
              <option value="patient">Paciente</option>
            </select>
          </Field>
          <Field label="Palavras mínimas para interrupção">
            <input
              name="min_interruption_words"
              type="number"
              min="1"
              max="5"
              defaultValue={String(turn.min_interruption_words ?? 1)}
            />
          </Field>
        </div>
        <Field label="Backchannels ignorados (vírgulas)">
          <input
            name="backchannels"
            defaultValue={
              Array.isArray(turn.ignore_backchannels)
                ? turn.ignore_backchannels.join(", ")
                : "hum, uhum, sim, tá, ok, certo, aham"
            }
          />
        </Field>
        <Field label="Keywords STT (vírgulas)">
          <input
            name="keywords"
            defaultValue={
              Array.isArray(stt.keywords) ? stt.keywords.join(", ") : ""
            }
          />
        </Field>
        <label className="check">
          <input
            type="checkbox"
            name="filler_enabled"
            defaultChecked={behavior.filler_enabled !== false}
          />{" "}
          Filler para operações lentas
        </label>
        <Field label="Frases de filler (separadas por |)">
          <input
            name="filler_phrases"
            defaultValue={
              Array.isArray(behavior.filler_phrases)
                ? behavior.filler_phrases.join(" | ")
                : "Só um instante. | Deixa eu verificar. | Um momento, por favor."
            }
          />
        </Field>
        <Field label="Número de transferência">
          <input
            name="transfer_number"
            type="tel"
            defaultValue={String(behavior.transfer_number ?? "")}
          />
        </Field>
        <Field label="Variáveis default (JSON)">
          <textarea
            name="variables"
            rows={5}
            defaultValue={JSON.stringify(draft.variables ?? {}, null, 2)}
          />
        </Field>
        <Field label="JSON da versão (somente leitura)">
          <textarea readOnly rows={8} value={JSON.stringify(draft, null, 2)} />
        </Field>
        <button className="save">Salvar configuração avançada</button>
      </form>
    </section>
  );
}

export default function Dashboard({
  tenantSlug,
  initialTestAgentId,
}: {
  tenantSlug: string;
  initialTestAgentId?: string;
}) {
  const [section, setSection] = useState<Section>("overview");
  const [agents, setAgents] = useState<Item[]>([]);
  const [agentTemplates, setAgentTemplates] = useState<AgentTemplate[]>([]);
  const [newAgentTemplate, setNewAgentTemplate] = useState("receptionist");
  const [calls, setCalls] = useState<Call[]>([]);
  const [knowledge, setKnowledge] = useState<Item[]>([]);
  const [selectedKnowledge, setSelectedKnowledge] = useState<Item | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [queryResults, setQueryResults] = useState<
    Array<Record<string, unknown>>
  >([]);
  const [tools, setTools] = useState<Item[]>([]);
  const [members, setMembers] = useState<Item[]>([]);
  const [apiKeys, setApiKeys] = useState<Item[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [role, setRole] = useState("viewer");
  const [widgetAgentId, setWidgetAgentId] = useState<string | null>(
    initialTestAgentId ?? null,
  );
  const [selectedAgent, setSelectedAgent] = useState<Item | null>(null);
  const [agentTab, setAgentTab] = useState<AgentTab>("prompt");
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([]);
  const [toolTestResult, setToolTestResult] = useState("");
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const callAudio = useRef<HTMLAudioElement>(null);

  function seekCall(offsetMs = 0) {
    if (!callAudio.current) return;
    callAudio.current.currentTime = Math.max(0, offsetMs) / 1000;
    void callAudio.current.play().catch(() => undefined);
  }

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const me = await api<{ tenant_id: string; role: string }>("me");
      const [a, templates, c] = await Promise.all([
        api<{ data: Item[] }>("agents"),
        api<{ data: AgentTemplate[] }>("agent-templates"),
        api<{ data: Call[] }>("calls"),
      ]);
      const canConfigure = ["owner", "admin"].includes(me.role);
      const [k, t, keys, memberResult] = canConfigure
        ? await Promise.all([
            api<{ data: Item[] }>("knowledge-bases"),
            api<{ data: Item[] }>("tools"),
            api<{ data: Item[] }>("api-keys"),
            api<{ data: Item[] }>(`tenants/${me.tenant_id}/members`),
          ])
        : [{ data: [] }, { data: [] }, { data: [] }, { data: [] }];
      setTenantId(me.tenant_id);
      setRole(me.role);
      setMembers(memberResult.data);
      setApiKeys(keys.data);
      setAgents(a.data);
      setAgentTemplates(templates.data);
      setCalls(c.data);
      setKnowledge(k.data);
      setTools(t.data);
      setNotice("");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Falha ao carregar dados",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);

  const today = new Date().toISOString().slice(0, 10);
  const todayCalls = calls.filter((call) =>
    String(call.started_at ?? "").startsWith(today),
  );
  const minutes = Math.round(
    calls.reduce((sum, call) => sum + Number(call.duration_s ?? 0), 0) / 60,
  );
  const active = calls.filter((call) =>
    ["queued", "ringing", "in_progress"].includes(call.status ?? ""),
  ).length;
  const completed = calls.filter((call) => call.status === "completed").length;
  const canConfigure = ["owner", "admin"].includes(role);

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const name = String(form.get("name") ?? "").trim();
    if (!name) return;
    try {
      const created = await api<Item>("agents", {
        method: "POST",
        body: JSON.stringify({ name, template_id: newAgentTemplate }),
      });
      formElement.reset();
      await refresh();
      await openAgent(created.id);
      setNotice(
        "Agente criado a partir do template. Revise o rascunho antes de publicar.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function openAgent(id: string, nextTab: AgentTab = "prompt") {
    const [detail, linked] = await Promise.all([
      api<Item>(`agents/${id}`),
      api<{ data: Item[] }>(`agents/${id}/draft/tools`),
    ]);
    setSelectedAgent(detail);
    setSelectedToolIds(linked.data.map((tool) => tool.id));
    setAgentTab(nextTab);
    setSection("agents");
  }
  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedAgent) return;
    const form = new FormData(event.currentTarget);
    const body = {
      system_prompt: String(form.get("system_prompt")),
      greeting: String(form.get("greeting")),
      language: String(form.get("language")),
      tts: {
        provider: "elevenlabs",
        model: "eleven_flash_v2_5",
        voice_id: String(form.get("voice_id")),
      },
      turn_config: {
        allow_interruptions: form.get("allow_interruptions") === "on",
      },
      behavior: {
        max_call_duration_s: Number(form.get("max_duration")),
        silence_timeout_s: Number(form.get("silence_timeout")),
      },
      knowledge_base_id: form.get("knowledge_base_id") || null,
      rag: { enabled: Boolean(form.get("knowledge_base_id")) },
    };
    try {
      await Promise.all([
        api(`agents/${selectedAgent.id}/draft`, {
          method: "PATCH",
          body: JSON.stringify(body),
        }),
        api(`agents/${selectedAgent.id}/draft/tools`, {
          method: "PUT",
          body: JSON.stringify({ tool_ids: selectedToolIds }),
        }),
      ]);
      await openAgent(selectedAgent.id, agentTab);
      setNotice("Rascunho e ferramentas salvos.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function publishAgent() {
    if (!selectedAgent) return;
    try {
      await api(`agents/${selectedAgent.id}/publish`, {
        method: "POST",
        body: "{}",
      });
      await refresh();
      await openAgent(selectedAgent.id, agentTab);
      setNotice("Versão publicada.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function saveAdvanced(patch: Record<string, unknown>) {
    if (!selectedAgent) return;
    try {
      await api(`agents/${selectedAgent.id}/draft`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      await openAgent(selectedAgent.id, "advanced");
      setNotice("Configuração avançada salva.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function setAgentStatus(status: string) {
    if (!selectedAgent) return;
    try {
      await api(`agents/${selectedAgent.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await refresh();
      await openAgent(selectedAgent.id, "advanced");
      setNotice(status === "paused" ? "Agente pausado." : "Agente reativado.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function deleteSelectedAgent() {
    if (!selectedAgent) return;
    if (!confirm(`Excluir ${selectedAgent.name}?`)) return;
    try {
      await api(`agents/${selectedAgent.id}`, { method: "DELETE" });
      setSelectedAgent(null);
      await refresh();
      setNotice("Agente excluído.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  function testAgent() {
    if (selectedAgent) setWidgetAgentId(selectedAgent.id);
  }
  async function openCall(id: string) {
    const detail = await api<Call>(`calls/${id}`);
    setSelectedCall(detail);
    setSection("calls");
  }
  async function openKnowledge(kb: Item) {
    setSelectedKnowledge(kb);
    setDocuments(
      (await api<{ data: Document[] }>(`knowledge-bases/${kb.id}/documents`))
        .data,
    );
    setQueryResults([]);
  }
  async function createKnowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const created = await api<Item>("knowledge-bases", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name") }),
      });
      event.currentTarget.reset();
      await refresh();
      await openKnowledge(created);
      setNotice("Base criada.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function ingestDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedKnowledge) return;
    const form = new FormData(event.currentTarget);
    const file = form.get("file") as File;
    const text = String(form.get("text") ?? "").trim();
    const url = String(form.get("url") ?? "").trim();
    try {
      let response: Response;
      if (file?.size) {
        const upload = new FormData();
        upload.set("file", file);
        response = await fetch(
          `/api/voiceos/knowledge-bases/${selectedKnowledge.id}/documents`,
          { method: "POST", body: upload },
        );
      } else {
        response = await fetch(
          `/api/voiceos/knowledge-bases/${selectedKnowledge.id}/documents`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              name: String(form.get("name") || url || "Documento"),
              text: text || undefined,
              url: url || undefined,
            }),
          },
        );
      }
      if (!response.ok)
        throw new Error(
          (await response.json().catch(() => ({})))?.detail?.message ??
            `HTTP ${response.status}`,
        );
      event.currentTarget.reset();
      await openKnowledge(selectedKnowledge);
      setNotice("Documento recebido; a ingestão está sendo processada.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function deleteDocument(documentId: string) {
    if (!selectedKnowledge) return;
    try {
      await api(
        `knowledge-bases/${selectedKnowledge.id}/documents/${documentId}`,
        { method: "DELETE" },
      );
      await openKnowledge(selectedKnowledge);
      setNotice("Documento removido.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function queryKnowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedKnowledge) return;
    const form = new FormData(event.currentTarget);
    try {
      const result = await api<{ data: Array<Record<string, unknown>> }>(
        `knowledge-bases/${selectedKnowledge.id}/query`,
        {
          method: "POST",
          body: JSON.stringify({
            query: form.get("query"),
            top_k: 5,
            min_score: 0.65,
          }),
        },
      );
      setQueryResults(result.data);
      setNotice(
        result.data.length
          ? "Busca vetorial concluída."
          : "Nenhum trecho atingiu o score mínimo.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function createTool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("tools", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description"),
          type: "webhook",
          parameters_schema: { type: "object", properties: {} },
          webhook: { url: form.get("url"), method: "POST", timeout_ms: 5000 },
        }),
      });
      event.currentTarget.reset();
      await refresh();
      setNotice(
        "Ferramenta criada; execute o teste antes de publicar um agente que a use.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function testTool(tool: Item) {
    try {
      const result = await api<Record<string, unknown>>(
        `tools/${tool.id}/test`,
        {
          method: "POST",
          body: JSON.stringify({
            arguments: {},
            session_variables: {},
            end_user: {},
          }),
        },
      );
      setToolTestResult(JSON.stringify(result, null, 2));
      await refresh();
      setNotice(`Teste de ${tool.name} concluído.`);
    } catch (error) {
      setToolTestResult(String(error));
      setNotice(String(error));
    }
  }
  async function inviteMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api(`tenants/${tenantId}/members`, {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          role: form.get("role"),
        }),
      });
      event.currentTarget.reset();
      await refresh();
      setNotice("Membro adicionado ao workspace.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function createApiKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const origin = String(form.get("origin") ?? "").trim();
    try {
      const result = await api<Item & { key: string }>("api-keys", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          scope: form.get("scope"),
          allowed_origins: origin ? [origin] : [],
        }),
      });
      event.currentTarget.reset();
      await refresh();
      setNotice(
        `Copie agora; esta chave não será mostrada novamente: ${result.key}`,
      );
    } catch (error) {
      setNotice(String(error));
    }
  }

  const draft = (selectedAgent?.draft ?? {}) as Record<string, unknown>;
  const stats = useMemo(
    () => [
      ["Chamadas hoje", todayCalls.length],
      ["Minutos", minutes],
      ["Concluídas", completed],
      ["Ao vivo", active],
    ],
    [todayCalls.length, minutes, completed, active],
  );

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          Voice<span>OS</span>
        </div>
        <div className="tenant">
          Workspace
          <br />
          <strong>{tenantSlug}</strong>
        </div>
        <nav>
          {sections.map(([id, label]) => (
            <button
              key={id}
              className={section === id ? "active" : ""}
              onClick={() => setSection(id)}
            >
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <main>
        <header className="top">
          <div>
            <div className="eyebrow">tenant / {tenantSlug}</div>
            <h1>{sections.find(([id]) => id === section)?.[1]}</h1>
          </div>
          <div className="topActions">
            <button className="secondary" onClick={() => void refresh()}>
              Atualizar
            </button>
            <button onClick={() => setSection("agents")}>Novo agente</button>
          </div>
        </header>
        {notice && (
          <div className="notice" role="status">
            <span>{notice}</span>
            <button onClick={() => setNotice("")}>×</button>
          </div>
        )}
        {widgetAgentId && (
          <VoiceWidget
            agentId={widgetAgentId}
            onNotice={setNotice}
            onClose={() => {
              setWidgetAgentId(null);
              void refresh();
            }}
          />
        )}
        {loading ? (
          <div className="loading">Carregando operação…</div>
        ) : (
          <>
            {section === "overview" && (
              <>
                <section className="stats">
                  {stats.map(([label, value]) => (
                    <article className="card" key={label}>
                      <span className="muted">{label}</span>
                      <strong className="value">{value}</strong>
                    </article>
                  ))}
                </section>
                <section className="split">
                  <article className="card">
                    <h2>Agentes</h2>
                    {agents.slice(0, 5).map((agent) => (
                      <button
                        className="row"
                        key={agent.id}
                        onClick={() => void openAgent(agent.id)}
                      >
                        <span>
                          <strong>{agent.name}</strong>
                          <small>{agent.status}</small>
                        </span>
                        <b>→</b>
                      </button>
                    ))}
                    {!agents.length && (
                      <Empty>Crie seu primeiro agente para iniciar.</Empty>
                    )}
                  </article>
                  <article className="card">
                    <h2>Chamadas recentes</h2>
                    {calls.slice(0, 6).map((call) => (
                      <button
                        className="row"
                        key={call.id}
                        onClick={() => void openCall(call.id)}
                      >
                        <span>
                          <strong>
                            {call.channel ?? "web"} · {call.status}
                          </strong>
                          <small>
                            {call.summary ??
                              new Date(
                                call.started_at ?? Date.now(),
                              ).toLocaleString("pt-BR")}
                          </small>
                        </span>
                        <b>→</b>
                      </button>
                    ))}
                    {!calls.length && (
                      <Empty>Nenhuma chamada registrada.</Empty>
                    )}
                  </article>
                </section>
              </>
            )}
            {section === "agents" && (
              <section className="workspace">
                <aside className="list card">
                  <h2>Agentes</h2>
                  <form className="inline" onSubmit={createAgent}>
                    <input name="name" placeholder="Nome do agente" required />
                    <button>+</button>
                  </form>
                  {agents.map((agent) => (
                    <button
                      className={`row ${selectedAgent?.id === agent.id ? "selected" : ""}`}
                      key={agent.id}
                      onClick={() => void openAgent(agent.id)}
                    >
                      <span>
                        <strong>{agent.name}</strong>
                        <small>{agent.status}</small>
                      </span>
                    </button>
                  ))}
                </aside>
                <article className="card editor">
                  {selectedAgent ? (
                    <>
                      <div className="editorHead">
                        <div>
                          <div className="eyebrow">editor do agente</div>
                          <h2>{selectedAgent.name}</h2>
                        </div>
                        <div>
                          <button
                            className="secondary"
                            onClick={() => void testAgent()}
                          >
                            Testar
                          </button>
                          <button onClick={() => void publishAgent()}>
                            Publicar
                          </button>
                        </div>
                      </div>
                      <div
                        className="tabs"
                        role="tablist"
                        aria-label="Editor do agente"
                      >
                        {agentTabs.map(([id, label]) => (
                          <button
                            type="button"
                            role="tab"
                            aria-selected={agentTab === id}
                            className={agentTab === id ? "active" : ""}
                            key={id}
                            onClick={() => setAgentTab(id)}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <form
                        className="formGrid"
                        onSubmit={saveAgent}
                        hidden={agentTab === "advanced"}
                      >
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "prompt"}
                        >
                          <Field label="Prompt do sistema">
                            <textarea
                              name="system_prompt"
                              defaultValue={String(draft.system_prompt ?? "")}
                              rows={8}
                            />
                          </Field>
                          <Field label="Saudação">
                            <textarea
                              name="greeting"
                              defaultValue={String(draft.greeting ?? "")}
                              rows={3}
                            />
                          </Field>
                        </fieldset>
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "voice"}
                        >
                          <div className="two">
                            <Field label="Idioma">
                              <input
                                name="language"
                                defaultValue={String(draft.language ?? "pt-BR")}
                              />
                            </Field>
                            <Field label="Voice ID">
                              <input
                                name="voice_id"
                                defaultValue={String(
                                  (
                                    draft.tts as
                                      | Record<string, unknown>
                                      | undefined
                                  )?.voice_id ?? "",
                                )}
                              />
                            </Field>
                          </div>
                        </fieldset>
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "conversation"}
                        >
                          <div className="two">
                            <Field label="Duração máxima (s)">
                              <input
                                name="max_duration"
                                type="number"
                                min="30"
                                defaultValue={String(
                                  (
                                    draft.behavior as
                                      | Record<string, unknown>
                                      | undefined
                                  )?.max_call_duration_s ?? 900,
                                )}
                              />
                            </Field>
                            <Field label="Silêncio (s)">
                              <input
                                name="silence_timeout"
                                type="number"
                                min="5"
                                defaultValue={String(
                                  (
                                    draft.behavior as
                                      | Record<string, unknown>
                                      | undefined
                                  )?.silence_timeout_s ?? 20,
                                )}
                              />
                            </Field>
                          </div>
                        </fieldset>
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "knowledge"}
                        >
                          <Field label="Base de conhecimento">
                            <select
                              name="knowledge_base_id"
                              defaultValue={String(
                                draft.knowledge_base_id ?? "",
                              )}
                            >
                              <option value="">Sem base</option>
                              {knowledge.map((kb) => (
                                <option value={kb.id} key={kb.id}>
                                  {kb.name}
                                </option>
                              ))}
                            </select>
                          </Field>
                        </fieldset>
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "tools"}
                        >
                          <fieldset className="toolPicker">
                            <legend>Tools do rascunho</legend>
                            {tools.map((tool) => (
                              <label className="check" key={tool.id}>
                                <input
                                  type="checkbox"
                                  checked={selectedToolIds.includes(tool.id)}
                                  onChange={(event) =>
                                    setSelectedToolIds((current) =>
                                      event.target.checked
                                        ? [...current, tool.id]
                                        : current.filter(
                                            (id) => id !== tool.id,
                                          ),
                                    )
                                  }
                                />{" "}
                                {tool.name}{" "}
                                <small>{String(tool.description ?? "")}</small>
                              </label>
                            ))}
                            {!tools.length && (
                              <small>
                                Crie ferramentas na seção Ferramentas.
                              </small>
                            )}
                          </fieldset>
                        </fieldset>
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "conversation"}
                        >
                          <label className="check">
                            <input
                              type="checkbox"
                              name="allow_interruptions"
                              defaultChecked={
                                (
                                  draft.turn_config as
                                    | Record<string, unknown>
                                    | undefined
                                )?.allow_interruptions !== false
                              }
                            />{" "}
                            Permitir interrupções (barge-in)
                          </label>
                        </fieldset>
                        <button className="save">Salvar rascunho</button>
                      </form>
                    </>
                  ) : (
                    <Empty>Selecione um agente ou crie um novo.</Empty>
                  )}
                </article>
              </section>
            )}
            {section === "calls" && (
              <section className="workspace">
                <aside className="list card">
                  <h2>Chamadas</h2>
                  {calls.map((call) => (
                    <button
                      className={`row ${selectedCall?.id === call.id ? "selected" : ""}`}
                      key={call.id}
                      onClick={() => void openCall(call.id)}
                    >
                      <span>
                        <strong>
                          {call.status} · {call.channel}
                        </strong>
                        <small>
                          {call.duration_s ?? 0}s ·{" "}
                          {call.summary ?? "Sem resumo"}
                        </small>
                      </span>
                    </button>
                  ))}
                </aside>
                <article className="card editor">
                  {selectedCall ? (
                    <>
                      <div className="eyebrow">detalhe da chamada</div>
                      <h2>{selectedCall.summary ?? selectedCall.id}</h2>
                      <div className="callMeta">
                        <span>
                          Status <b>{selectedCall.status}</b>
                        </span>
                        <span>
                          Duração <b>{selectedCall.duration_s ?? 0}s</b>
                        </span>
                        <span>
                          Canal <b>{selectedCall.channel}</b>
                        </span>
                      </div>
                      {(selectedCall.recording ||
                        selectedCall.recordings?.[0]) && (
                        <audio
                          ref={callAudio}
                          controls
                          src={`/api/voiceos/calls/${selectedCall.id}/recording`}
                        />
                      )}
                      <div className="transcript">
                        {selectedCall.turns?.map((turn, index) => (
                          <button
                            type="button"
                            className={`turn ${turn.role}`}
                            key={turn.id ?? index}
                            onClick={() => seekCall(turn.audio_offset_ms)}
                            aria-label={`Ir para ${Math.round((turn.audio_offset_ms ?? 0) / 1000)} segundos: ${turn.text}`}
                          >
                            <b>{turn.role === "user" ? "Pessoa" : "Agente"}</b>
                            <span>{turn.text}</span>
                            <small>
                              {Math.round((turn.audio_offset_ms ?? 0) / 1000)}s
                            </small>
                          </button>
                        ))}
                        {!selectedCall.turns?.length && (
                          <Empty>
                            A transcrição aparecerá aqui durante a chamada.
                          </Empty>
                        )}
                      </div>
                    </>
                  ) : (
                    <Empty>
                      Selecione uma chamada para ver áudio e transcrição
                      sincronizada.
                    </Empty>
                  )}
                </article>
              </section>
            )}
            {section === "knowledge" && (
              <section className="workspace">
                <aside className="list card">
                  <h2>Bases de conhecimento</h2>
                  <form className="inline" onSubmit={createKnowledge}>
                    <input name="name" placeholder="Nome da base" required />
                    <button>+</button>
                  </form>
                  {knowledge.map((kb) => (
                    <button
                      className={`row ${selectedKnowledge?.id === kb.id ? "selected" : ""}`}
                      key={kb.id}
                      onClick={() => void openKnowledge(kb)}
                    >
                      <span>
                        <strong>{kb.name}</strong>
                        <small>
                          {String(
                            kb.embedding_model ?? "text-embedding-3-small",
                          )}
                        </small>
                      </span>
                      <span className="pill ok">
                        {String(kb.status ?? "ativa")}
                      </span>
                    </button>
                  ))}
                </aside>
                <article className="card editor">
                  {selectedKnowledge ? (
                    <>
                      <div className="eyebrow">base de conhecimento</div>
                      <h2>{selectedKnowledge.name}</h2>
                      <form
                        className="formGrid ingest"
                        onSubmit={ingestDocument}
                      >
                        <div className="two">
                          <Field label="Arquivo PDF, DOCX ou HTML">
                            <input
                              name="file"
                              type="file"
                              accept=".pdf,.docx,.html,.htm,.txt"
                            />
                          </Field>
                          <Field label="URL">
                            <input
                              name="url"
                              type="url"
                              placeholder="https://…"
                            />
                          </Field>
                        </div>
                        <Field label="Nome (texto/URL)">
                          <input name="name" placeholder="FAQ comercial" />
                        </Field>
                        <Field label="Ou cole o conteúdo">
                          <textarea name="text" rows={4} />
                        </Field>
                        <button className="save">Adicionar documento</button>
                      </form>
                      <h2>Documentos</h2>
                      {documents.map((document) => (
                        <div className="row static" key={document.id}>
                          <span>
                            <strong>{document.name}</strong>
                            <small>
                              {document.source_type} ·{" "}
                              {document.chunk_count ?? 0} chunks
                              {document.error ? ` · ${document.error}` : ""}
                            </small>
                          </span>
                          <span>
                            <span
                              className={`pill ${document.status === "ready" ? "ok" : ""}`}
                            >
                              {document.status}
                            </span>{" "}
                            <button
                              className="iconDanger"
                              onClick={() => void deleteDocument(document.id)}
                            >
                              ×
                            </button>
                          </span>
                        </div>
                      ))}
                      {!documents.length && (
                        <Empty>Nenhum documento nesta base.</Empty>
                      )}
                      <h2>Consultar base</h2>
                      <form className="inline" onSubmit={queryKnowledge}>
                        <input
                          name="query"
                          placeholder="Faça uma pergunta para validar os chunks"
                          required
                        />
                        <button>Buscar</button>
                      </form>
                      {queryResults.map((result, index) => (
                        <div
                          className="queryResult"
                          key={String(result.id ?? index)}
                        >
                          <b>score {Number(result.score ?? 0).toFixed(3)}</b>
                          <p>{String(result.content ?? "")}</p>
                        </div>
                      ))}
                    </>
                  ) : (
                    <Empty>
                      Selecione ou crie uma base para adicionar documentos e
                      testar a recuperação.
                    </Empty>
                  )}
                </article>
              </section>
            )}
            {section === "tools" && (
              <section className="split">
                <article className="card">
                  <h2>Ferramentas</h2>
                  {tools.map((tool) => (
                    <div className="row static" key={tool.id}>
                      <span>
                        <strong>{tool.name}</strong>
                        <small>{String(tool.description ?? tool.type)}</small>
                      </span>
                      <span>
                        <button
                          className="secondary compact"
                          onClick={() => void testTool(tool)}
                        >
                          Testar
                        </button>{" "}
                        <span
                          className={`pill ${tool.last_test_ok_at ? "ok" : ""}`}
                        >
                          {tool.last_test_ok_at ? "testada" : "pendente"}
                        </span>
                      </span>
                    </div>
                  ))}
                  {toolTestResult && (
                    <pre className="testResult">{toolTestResult}</pre>
                  )}
                </article>
                <article className="card">
                  <h2>Novo webhook</h2>
                  <form className="formGrid" onSubmit={createTool}>
                    <Field label="Nome snake_case">
                      <input name="name" required pattern="[a-z0-9_]+" />
                    </Field>
                    <Field label="Descrição">
                      <input name="description" required maxLength={300} />
                    </Field>
                    <Field label="URL HTTPS">
                      <input name="url" type="url" required />
                    </Field>
                    <button>Criar ferramenta</button>
                  </form>
                </article>
              </section>
            )}
            {section === "members" && (
              <section className="split">
                <article className="card">
                  <h2>Membros</h2>
                  {members.map((member) => (
                    <div className="row static" key={member.id}>
                      <span>
                        <strong>{String(member.name ?? member.email)}</strong>
                        <small>{String(member.email)}</small>
                      </span>
                      <span className="pill ok">{String(member.role)}</span>
                    </div>
                  ))}
                  {!members.length && <Empty>Nenhum membro listado.</Empty>}
                </article>
                <article className="card">
                  <h2>Adicionar membro</h2>
                  <form className="formGrid" onSubmit={inviteMember}>
                    <Field label="E-mail">
                      <input name="email" type="email" required />
                    </Field>
                    <Field label="Papel">
                      <select name="role">
                        <option value="viewer">Viewer</option>
                        <option value="operator">Operator</option>
                        <option value="developer">Developer</option>
                        <option value="admin">Admin</option>
                      </select>
                    </Field>
                    <button>Adicionar</button>
                  </form>
                </article>
              </section>
            )}
            {section === "settings" && (
              <section className="split">
                <article className="card">
                  <h2>Integrações</h2>
                  <p>Google Calendar e Gmail</p>
                  <button
                    className="secondary"
                    onClick={async () => {
                      try {
                        const result = await api<{ url: string }>(
                          "integrations/google/connect",
                        );
                        location.href = result.url;
                      } catch (error) {
                        setNotice(String(error));
                      }
                    }}
                  >
                    Conectar Google
                  </button>
                  <h2>Chaves existentes</h2>
                  {apiKeys.map((key) => (
                    <div className="row static" key={key.id}>
                      <span>
                        <strong>{key.name}</strong>
                        <small>
                          {String(key.prefix)}… · {String(key.scope)}
                        </small>
                      </span>
                      <span className={`pill ${key.revoked_at ? "" : "ok"}`}>
                        {key.revoked_at ? "revogada" : "ativa"}
                      </span>
                    </div>
                  ))}
                </article>
                <article className="card">
                  <h2>Nova API key</h2>
                  <p className="muted">
                    A chave completa é exibida somente uma vez; apenas SHA-256 é
                    armazenado.
                  </p>
                  <form className="formGrid" onSubmit={createApiKey}>
                    <Field label="Nome">
                      <input name="name" required />
                    </Field>
                    <Field label="Escopo">
                      <select name="scope">
                        <option value="secret">Secret</option>
                        <option value="public">Public/widget</option>
                      </select>
                    </Field>
                    <Field label="Origem permitida (obrigatória para public)">
                      <input
                        name="origin"
                        type="url"
                        placeholder="https://cliente.com"
                      />
                    </Field>
                    <button>Criar chave</button>
                  </form>
                </article>
              </section>
            )}
            {section === "agents" &&
              selectedAgent &&
              canConfigure &&
              agentTab === "advanced" && (
                <AgentAdvancedPanel
                  key={String(draft.id ?? selectedAgent.id)}
                  agent={selectedAgent}
                  draft={draft}
                  onSave={saveAdvanced}
                  onStatus={setAgentStatus}
                  onDelete={deleteSelectedAgent}
                />
              )}
            {section === "calls" && selectedCall && (
              <CallEvidence call={selectedCall} />
            )}
            {section === "agents" && canConfigure && (
              <aside className="templateDock card">
                <b>Template para o próximo agente</b>
                <select
                  aria-label="Template do agente"
                  value={newAgentTemplate}
                  onChange={(event) => setNewAgentTemplate(event.target.value)}
                >
                  {agentTemplates.map((template) => (
                    <option value={template.id} key={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
                <small>
                  {
                    agentTemplates.find(
                      (template) => template.id === newAgentTemplate,
                    )?.description
                  }
                </small>
              </aside>
            )}
          </>
        )}
      </main>
    </div>
  );
}
