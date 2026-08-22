"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { extractPromptVariables } from "../../../lib/prompt-utils";
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
type AvailableNumber = {
  e164: string;
  friendly_name?: string;
  locality?: string;
  region?: string;
  capabilities?: Record<string, boolean>;
};
type Campaign = Item & {
  agent_id?: string;
  schedule?: Record<string, unknown>;
  stats?: Record<string, number>;
};
type BillingPlan = Record<string, unknown> & {
  code: string;
  name: string;
  included_minutes: number;
  monthly_price_cents: number;
  subscription_status?: string;
};
type BillingUsage = {
  minutes: number;
  included_minutes: number;
  overage_minutes: number;
  estimated_overage_cents: number;
};
type Section =
  | "overview"
  | "agents"
  | "calls"
  | "live"
  | "campaigns"
  | "knowledge"
  | "tools"
  | "numbers"
  | "members"
  | "billing"
  | "settings";
type AgentTab =
  | "prompt"
  | "voice"
  | "conversation"
  | "knowledge"
  | "tools"
  | "channels"
  | "advanced";

const agentTabs: Array<[AgentTab, string]> = [
  ["prompt", "Prompt"],
  ["voice", "Voz"],
  ["conversation", "Conversa"],
  ["knowledge", "Conhecimento"],
  ["tools", "Tools"],
  ["channels", "Canais"],
  ["advanced", "Avançado"],
];

const sections: Array<[Section, string]> = [
  ["overview", "Visão geral"],
  ["agents", "Agentes"],
  ["calls", "Chamadas"],
  ["live", "Ao vivo"],
  ["campaigns", "Campanhas"],
  ["knowledge", "Conhecimento"],
  ["tools", "Ferramentas"],
  ["numbers", "Números"],
  ["members", "Membros"],
  ["billing", "Billing"],
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
      data?.error?.message ??
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
    let businessHours: Record<string, unknown>;
    try {
      variables = JSON.parse(String(form.get("variables") || "{}")) as Record<
        string,
        unknown
      >;
      businessHours = JSON.parse(
        String(form.get("business_hours") || "{}"),
      ) as Record<string, unknown>;
    } catch {
      throw new Error("Variáveis e horário devem ser objetos JSON válidos.");
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
        end_call_phrases: String(form.get("end_call_phrases") || "")
          .split("|")
          .map((value) => value.trim())
          .filter(Boolean),
        silence_prompt: String(form.get("silence_prompt") || ""),
        business_hours:
          form.get("business_hours_enabled") === "on" ? businessHours : null,
        out_of_hours_message: String(form.get("out_of_hours_message") || ""),
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
        <Field label="Frases de encerramento (separadas por |)">
          <input
            name="end_call_phrases"
            defaultValue={
              Array.isArray(behavior.end_call_phrases)
                ? behavior.end_call_phrases.join(" | ")
                : "Obrigado pelo contato. | Até logo. | Tenha um ótimo dia."
            }
          />
        </Field>
        <Field label="Prompt após silêncio">
          <input
            name="silence_prompt"
            defaultValue={String(
              behavior.silence_prompt ??
                "Você ainda está aí? Posso ajudar em mais alguma coisa?",
            )}
          />
        </Field>
        <label className="check">
          <input
            type="checkbox"
            name="business_hours_enabled"
            defaultChecked={Boolean(behavior.business_hours)}
          />{" "}
          Aplicar horário de funcionamento
        </label>
        <Field label="Horário de funcionamento (JSON)">
          <textarea
            name="business_hours"
            rows={5}
            defaultValue={JSON.stringify(
              behavior.business_hours ?? {
                timezone: "America/Sao_Paulo",
                weekdays: { mon_fri: [["09:00", "18:00"]] },
              },
              null,
              2,
            )}
          />
        </Field>
        <Field label="Mensagem fora do horário">
          <textarea
            name="out_of_hours_message"
            rows={2}
            defaultValue={String(
              behavior.out_of_hours_message ??
                "Nosso atendimento humano está fechado agora. Posso registrar seu contato para retorno?",
            )}
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
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignContacts, setCampaignContacts] = useState<Record<string, string>>({});
  const [knowledge, setKnowledge] = useState<Item[]>([]);
  const [selectedKnowledge, setSelectedKnowledge] = useState<Item | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [queryResults, setQueryResults] = useState<
    Array<Record<string, unknown>>
  >([]);
  const [tools, setTools] = useState<Item[]>([]);
  const [secrets, setSecrets] = useState<Item[]>([]);
  const [phoneNumbers, setPhoneNumbers] = useState<Item[]>([]);
  const [availableNumbers, setAvailableNumbers] = useState<AvailableNumber[]>(
    [],
  );
  const [members, setMembers] = useState<Item[]>([]);
  const [apiKeys, setApiKeys] = useState<Item[]>([]);
  const [billingPlan, setBillingPlan] = useState<BillingPlan | null>(null);
  const [billingUsage, setBillingUsage] = useState<BillingUsage | null>(null);
  const [invoices, setInvoices] = useState<Item[]>([]);
  const [tenant, setTenant] = useState<Item | null>(null);
  const [tenantId, setTenantId] = useState("");
  const [role, setRole] = useState("viewer");
  const [widgetAgentId, setWidgetAgentId] = useState<string | null>(
    initialTestAgentId ?? null,
  );
  const [selectedAgent, setSelectedAgent] = useState<Item | null>(null);
  const [agentVersions, setAgentVersions] = useState<Item[]>([]);
  const [agentTab, setAgentTab] = useState<AgentTab>("prompt");
  const [promptValue, setPromptValue] = useState("");
  const [improvingPrompt, setImprovingPrompt] = useState(false);
  const [voices, setVoices] = useState<Item[]>([]);
  const [voiceProviderConfigured, setVoiceProviderConfigured] = useState(false);
  const [voiceId, setVoiceId] = useState("");
  const [greetingValue, setGreetingValue] = useState("");
  const [voicePreviewUrl, setVoicePreviewUrl] = useState("");
  const [previewingVoice, setPreviewingVoice] = useState(false);
  const [agentKnowledgeId, setAgentKnowledgeId] = useState("");
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([]);
  const [toolTestResult, setToolTestResult] = useState("");
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [liveEvents, setLiveEvents] = useState<Array<Record<string, unknown>>>([]);
  const [watchedCallId, setWatchedCallId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const callAudio = useRef<HTMLAudioElement>(null);
  const liveSource = useRef<EventSource | null>(null);
  const operatorRoom = useRef<{ disconnect: () => Promise<void> | void } | null>(null);

  useEffect(
    () => () => {
      liveSource.current?.close();
      void operatorRoom.current?.disconnect();
    },
    [],
  );

  function seekCall(offsetMs = 0) {
    if (!callAudio.current) return;
    callAudio.current.currentTime = Math.max(0, offsetMs) / 1000;
    void callAudio.current.play().catch(() => undefined);
  }

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const me = await api<{ tenant_id: string; role: string }>("me");
      const [a, templates, c, tenantResult, planResult, usageResult, invoiceResult] = await Promise.all([
        api<{ data: Item[] }>("agents"),
        api<{ data: AgentTemplate[] }>("agent-templates"),
        api<{ data: Call[] }>("calls"),
        api<Item>(`tenants/${me.tenant_id}`),
        api<BillingPlan>("billing/plan"),
        api<BillingUsage>("billing/usage"),
        api<{ data: Item[] }>("billing/invoices"),
      ]);
      const canConfigure = ["owner", "admin"].includes(me.role);
      const [k, t, keys, memberResult, voiceResult, secretResult, phoneResult, campaignResult] =
        canConfigure
          ? await Promise.all([
              api<{ data: Item[] }>("knowledge-bases"),
              api<{ data: Item[] }>("tools"),
              api<{ data: Item[] }>("api-keys"),
              api<{ data: Item[] }>(`tenants/${me.tenant_id}/members`),
              api<{ data: Item[]; configured: boolean }>("voices"),
              api<{ data: Item[] }>("secrets"),
              api<{ data: Item[] }>("phone-numbers"),
              api<{ data: Campaign[] }>("campaigns"),
            ])
          : [
              { data: [] },
              { data: [] },
              { data: [] },
              { data: [] },
              { data: [] },
              { data: [], configured: false },
              { data: [] },
              { data: [] },
            ];
      setTenantId(me.tenant_id);
      setTenant(tenantResult);
      setRole(me.role);
      setMembers(memberResult.data);
      setApiKeys(keys.data);
      setBillingPlan(planResult);
      setBillingUsage(usageResult);
      setInvoices(invoiceResult.data);
      setAgents(a.data);
      setAgentTemplates(templates.data);
      setCalls(c.data);
      setKnowledge(k.data);
      setTools(t.data);
      setSecrets(secretResult.data);
      setPhoneNumbers(phoneResult.data);
      setCampaigns(campaignResult.data);
      setVoices(voiceResult.data);
      setVoiceProviderConfigured(Boolean(voiceResult.configured));
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
  const ownerCount = members.filter((member) => member.role === "owner").length;

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
    const [detail, linked, versions] = await Promise.all([
      api<Item>(`agents/${id}`),
      api<{ data: Item[] }>(`agents/${id}/draft/tools`),
      api<{ data: Item[] }>(`agents/${id}/versions`),
    ]);
    setSelectedAgent(detail);
    setAgentVersions(versions.data);
    setSelectedToolIds(linked.data.map((tool) => tool.id));
    setPromptValue(
      String(
        (detail.draft as Record<string, unknown> | undefined)?.system_prompt ??
          "",
      ),
    );
    setGreetingValue(
      String(
        (detail.draft as Record<string, unknown> | undefined)?.greeting ?? "",
      ),
    );
    setVoiceId(
      String(
        (
          (detail.draft as Record<string, unknown> | undefined)?.tts as
            Record<string, unknown> | undefined
        )?.voice_id ?? "",
      ),
    );
    setVoicePreviewUrl("");
    setAgentKnowledgeId(
      String(
        (detail.draft as Record<string, unknown> | undefined)
          ?.knowledge_base_id ?? "",
      ),
    );
    setAgentTab(nextTab);
    setSection("agents");
  }
  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedAgent) return;
    const form = new FormData(event.currentTarget);
    const existingTts = ((
      selectedAgent.draft as Record<string, unknown> | undefined
    )?.tts ?? {}) as Record<string, unknown>;
    const existingRag = ((
      selectedAgent.draft as Record<string, unknown> | undefined
    )?.rag ?? {}) as Record<string, unknown>;
    const body = {
      system_prompt: String(form.get("system_prompt")),
      greeting: String(form.get("greeting")),
      language: String(form.get("language")),
      tts: {
        ...existingTts,
        provider: "elevenlabs",
        model: "eleven_flash_v2_5",
        voice_id: String(form.get("voice_id")),
        speed: Number(form.get("voice_speed")),
        stability: Number(form.get("voice_stability")),
      },
      turn_config: {
        allow_interruptions: form.get("allow_interruptions") === "on",
      },
      behavior: {
        max_call_duration_s: Number(form.get("max_duration")),
        silence_timeout_s: Number(form.get("silence_timeout")),
      },
      knowledge_base_id: form.get("knowledge_base_id") || null,
      rag: {
        ...existingRag,
        enabled: Boolean(form.get("knowledge_base_id")),
        top_k: Number(form.get("rag_top_k")),
        min_score: Number(form.get("rag_min_score")),
      },
    };
    try {
      setNotice("Salvando rascunho…");
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
  async function rollbackAgent(versionId: string) {
    if (!selectedAgent) return;
    try {
      await api(`agents/${selectedAgent.id}/rollback`, {
        method: "POST",
        body: JSON.stringify({ version_id: versionId }),
      });
      await refresh();
      await openAgent(selectedAgent.id, agentTab);
      setNotice(
        "Rollback aplicado em um novo rascunho. Revise antes de publicar.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function improvePrompt() {
    if (!selectedAgent || promptValue.trim().length < 20) return;
    setImprovingPrompt(true);
    try {
      const result = await api<{ improved_prompt: string }>(
        `agents/${selectedAgent.id}/draft/improve-prompt`,
        { method: "POST", body: JSON.stringify({ prompt: promptValue }) },
      );
      setPromptValue(result.improved_prompt);
      setNotice("Sugestão gerada. Revise e salve o rascunho para aplicar.");
    } catch (error) {
      setNotice(String(error));
    } finally {
      setImprovingPrompt(false);
    }
  }
  async function previewVoice() {
    if (!voiceId || !greetingValue.trim()) return;
    setPreviewingVoice(true);
    try {
      const response = await fetch(
        `/api/voiceos/voices/${encodeURIComponent(voiceId)}/preview`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ text: greetingValue, speed: 1 }),
        },
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data?.error?.message ?? `HTTP ${response.status}`);
      }
      if (voicePreviewUrl) URL.revokeObjectURL(voicePreviewUrl);
      setVoicePreviewUrl(URL.createObjectURL(await response.blob()));
      setNotice("Preview de voz sintetizado.");
    } catch (error) {
      setNotice(String(error));
    } finally {
      setPreviewingVoice(false);
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
  async function filterCalls(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const query = new URLSearchParams();
    for (const name of ["q", "status", "channel", "agent_id", "from", "to"]) {
      const value = String(form.get(name) ?? "").trim();
      if (value) query.set(name, value);
    }
    try {
      const result = await api<{ data: Call[] }>(`calls?${query.toString()}`);
      setCalls(result.data);
      setSelectedCall(null);
      setNotice(`${result.data.length} chamada(s) encontrada(s).`);
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function clearCallFilters(form: HTMLFormElement) {
    form.reset();
    try {
      const result = await api<{ data: Call[] }>("calls");
      setCalls(result.data);
      setSelectedCall(null);
      setNotice("Filtros de chamadas removidos.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  function downloadTranscript(call: Call) {
    const content = (call.turns ?? [])
      .map((turn) => {
        const totalSeconds = Math.floor((turn.audio_offset_ms ?? 0) / 1000);
        const timestamp = new Date(totalSeconds * 1000)
          .toISOString()
          .slice(11, 19);
        return `[${timestamp}] ${turn.role === "user" ? "Pessoa" : "Agente"}: ${turn.text}`;
      })
      .join("\n");
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/plain;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `voiceos-${call.id}-transcript.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }
  async function copyCallId(callId: string) {
    try {
      await navigator.clipboard.writeText(callId);
      setNotice("ID da chamada copiado.");
    } catch {
      setNotice(`ID da chamada: ${callId}`);
    }
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
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const parametersSchema = JSON.parse(
        String(form.get("parameters_schema") || "{}"),
      ) as Record<string, unknown>;
      const headers = JSON.parse(String(form.get("headers") || "{}")) as Record<
        string,
        unknown
      >;
      const bodyTemplate = JSON.parse(
        String(form.get("body_template") || "{}"),
      ) as Record<string, unknown>;
      const responseMapping = JSON.parse(
        String(form.get("response_mapping") || "{}"),
      ) as Record<string, unknown>;
      const authType = String(form.get("auth_type") || "none");
      const secretId = String(form.get("secret_id") || "");
      await api("tools", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description"),
          type: "webhook",
          parameters_schema: parametersSchema,
          webhook: {
            url: form.get("url"),
            method: form.get("method"),
            headers,
            auth:
              authType === "none"
                ? { type: "none" }
                : {
                    type: authType,
                    secret_id: secretId,
                    name: form.get("auth_header") || "X-API-Key",
                  },
            timeout_ms: Number(form.get("timeout_ms")),
            body_template: bodyTemplate,
            response_mapping: responseMapping,
          },
          speak_before: form.get("speak_before") || null,
          async: form.get("async") === "on",
        }),
      });
      formElement.reset();
      await refresh();
      setNotice(
        "Ferramenta criada; execute o teste antes de publicar um agente que a use.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function testTool(
    tool: Item,
    arguments_: Record<string, unknown> = {},
  ) {
    try {
      const result = await api<Record<string, unknown>>(
        `tools/${tool.id}/test`,
        {
          method: "POST",
          body: JSON.stringify({
            arguments: arguments_,
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
  async function updateMember(userId: string, role: string) {
    try {
      await api(`tenants/${tenantId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      await refresh();
      setNotice("Papel do membro atualizado.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function removeMember(userId: string) {
    try {
      await api(`tenants/${tenantId}/members/${userId}`, { method: "DELETE" });
      await refresh();
      setNotice("Membro removido do workspace.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function updateTenant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api(`tenants/${tenantId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: form.get("name"),
          settings: {
            timezone: form.get("timezone"),
            recording_enabled: form.get("recording_enabled") === "on",
            retention_days: Number(form.get("retention_days")),
          },
        }),
      });
      await refresh();
      setNotice("Configurações gerais salvas.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function revokeApiKey(keyId: string) {
    try {
      await api(`api-keys/${keyId}`, { method: "DELETE" });
      await refresh();
      setNotice("Chave de API revogada.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function createSecret(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api("secrets", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          value: form.get("value"),
        }),
      });
      formElement.reset();
      await refresh();
      setNotice("Secret criptografado e salvo.");
    } catch (error) {
      setNotice(String(error));
    }
  }
  async function deleteSecret(secretId: string) {
    try {
      await api(`secrets/${secretId}`, { method: "DELETE" });
      await refresh();
      setNotice("Secret removido.");
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

  async function searchPhoneNumbers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const areaCode = String(form.get("area_code") ?? "").trim();
    try {
      const result = await api<{ data: AvailableNumber[] }>(
        `phone-numbers/available?country=BR&area_code=${encodeURIComponent(areaCode)}`,
      );
      setAvailableNumbers(result.data);
      setNotice(
        result.data.length
          ? `${result.data.length} número(s) disponível(is).`
          : "Nenhum número disponível para este DDD.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function purchasePhoneNumber(e164: string) {
    try {
      await api("phone-numbers", {
        method: "POST",
        body: JSON.stringify({ e164 }),
      });
      setAvailableNumbers((items) =>
        items.filter((item) => item.e164 !== e164),
      );
      await refresh();
      setNotice(
        `${e164} comprado. Atribua-o a um agente para receber chamadas.`,
      );
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function assignPhoneNumber(numberId: string, agentId: string) {
    try {
      await api(`phone-numbers/${numberId}`, {
        method: "PATCH",
        body: JSON.stringify({ agent_id: agentId || null }),
      });
      await refresh();
      setNotice(
        agentId
          ? "Número atribuído e dispatch SIP atualizado."
          : "Número desvinculado.",
      );
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function releasePhoneNumber(numberId: string) {
    try {
      await api(`phone-numbers/${numberId}`, { method: "DELETE" });
      await refresh();
      setNotice("Número liberado no provedor e dispatch SIP removido.");
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function createCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api("campaigns", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          name: form.get("name"),
          agent_id: form.get("agent_id"),
          schedule: {
            timezone: form.get("timezone"),
            days: [0, 1, 2, 3, 4],
            window: { start: form.get("start"), end: form.get("end") },
            max_concurrency: Number(form.get("max_concurrency") ?? 1),
            retry_policy: { max_attempts: 3, delays_s: [300, 1800, 7200] },
          },
        }),
      });
      formElement.reset();
      await refresh();
      setNotice("Campanha criada como rascunho.");
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function importCampaignContacts(campaignId: string, raw: string) {
    const contacts = raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [phone, name] = line.split(",").map((part) => part.trim());
        return { phone, name: name || undefined, variables: {} };
      });
    try {
      await api(`campaigns/${campaignId}/contacts`, {
        method: "POST",
        body: JSON.stringify({ contacts }),
      });
      await refresh();
      setNotice(`${contacts.length} contato(s) importado(s).`);
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function campaignAction(campaignId: string, action: string) {
    try {
      await api(`campaigns/${campaignId}/${action}`, { method: "POST" });
      await refresh();
      setNotice(`AÃ§Ã£o ${action} aplicada Ã  campanha.`);
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function upgradePlan(planCode: string) {
    try {
      const result = await api<{ url: string }>("billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_code: planCode }),
      });
      window.location.assign(result.url);
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function openBillingPortal() {
    try {
      const result = await api<{ url: string }>("billing/portal", { method: "POST" });
      window.location.assign(result.url);
    } catch (error) {
      setNotice(String(error));
    }
  }

  function watchLive(callId: string) {
    liveSource.current?.close();
    setWatchedCallId(callId);
    setLiveEvents([]);
    const source = new EventSource(`/api/voiceos/calls/${callId}/live`);
    source.onmessage = (event) => {
      const item = JSON.parse(event.data) as Record<string, unknown>;
      setLiveEvents((events) => [...events.slice(-99), item]);
      if (item.type === "transfer.requested") {
        const context = new AudioContext();
        const oscillator = context.createOscillator();
        oscillator.connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + 0.18);
      }
    };
    source.onerror = () => setNotice("A transmissÃ£o ao vivo foi interrompida; reconecte para continuar.");
    liveSource.current = source;
  }

  async function takeoverCall(call: Call) {
    try {
      const phoneChannel = call.channel?.startsWith("phone");
      const extension = phoneChannel ? window.prompt("Ramal do operador em formato +E164") : null;
      if (phoneChannel && !extension) return;
      const result = await api<{ mode: string; livekit_url?: string; token?: string }>(
        `calls/${call.id}/takeover`,
        { method: "POST", body: JSON.stringify({ operator_extension: extension || null }) },
      );
      if (result.mode === "web" && result.livekit_url && result.token) {
        await operatorRoom.current?.disconnect();
        const { Room } = await import("livekit-client");
        const room = new Room();
        await room.connect(result.livekit_url, result.token);
        await room.localParticipant.setMicrophoneEnabled(true);
        operatorRoom.current = room;
      }
      setNotice(phoneChannel ? "Ramal conectado Ã  sala da chamada." : "Microfone do operador conectado Ã  chamada.");
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
                      <details className="versionHistory">
                        <summary>
                          Versões e rollback ({agentVersions.length})
                        </summary>
                        {agentVersions.map((version) => (
                          <div className="row static" key={version.id}>
                            <span>
                              <strong>
                                v{String(version.version ?? "rascunho")}
                              </strong>
                              <small>
                                {version.published_at
                                  ? `Publicada em ${new Date(String(version.published_at)).toLocaleString("pt-BR")}`
                                  : "Rascunho atual"}
                              </small>
                            </span>
                            {Boolean(version.published_at) && (
                              <button
                                type="button"
                                className="secondary compact"
                                onClick={() => void rollbackAgent(version.id)}
                              >
                                Restaurar como rascunho
                              </button>
                            )}
                          </div>
                        ))}
                      </details>
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
                              value={promptValue}
                              onChange={(event) =>
                                setPromptValue(event.target.value)
                              }
                              maxLength={6000}
                              rows={8}
                            />
                          </Field>
                          <div className="promptMeta">
                            <small>
                              {promptValue.length.toLocaleString("pt-BR")} /
                              6.000 caracteres
                            </small>
                            <button
                              type="button"
                              className="secondary compact"
                              disabled={
                                improvingPrompt ||
                                promptValue.trim().length < 20
                              }
                              onClick={() => void improvePrompt()}
                            >
                              {improvingPrompt
                                ? "Melhorando…"
                                : "Melhorar com IA"}
                            </button>
                          </div>
                          <div
                            className="variablePanel"
                            aria-label="Variáveis detectadas"
                          >
                            <b>Variáveis detectadas</b>
                            {extractPromptVariables(promptValue).map(
                              (variable) => (
                                <span
                                  className="pill ok"
                                  key={variable}
                                >{`{{ ${variable} }}`}</span>
                              ),
                            )}
                            {!extractPromptVariables(promptValue).length && (
                              <small>Nenhuma variável Jinja detectada.</small>
                            )}
                          </div>
                          <Field label="Saudação">
                            <textarea
                              name="greeting"
                              value={greetingValue}
                              onChange={(event) =>
                                setGreetingValue(event.target.value)
                              }
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
                                value={voiceId}
                                onChange={(event) =>
                                  setVoiceId(event.target.value)
                                }
                                list="voice-catalog"
                              />
                              <datalist id="voice-catalog">
                                {voices.map((voice) => (
                                  <option value={voice.id} key={voice.id}>
                                    {voice.name}
                                  </option>
                                ))}
                              </datalist>
                            </Field>
                          </div>
                          <div className="two">
                            <Field label="Velocidade da voz">
                              <input
                                name="voice_speed"
                                type="number"
                                min="0.7"
                                max="1.2"
                                step="0.05"
                                defaultValue={String(
                                  (
                                    draft.tts as
                                      Record<string, unknown> | undefined
                                  )?.speed ?? 1,
                                )}
                              />
                            </Field>
                            <Field label="Estabilidade">
                              <input
                                name="voice_stability"
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                defaultValue={String(
                                  (
                                    draft.tts as
                                      Record<string, unknown> | undefined
                                  )?.stability ?? 0.5,
                                )}
                              />
                            </Field>
                          </div>
                          <div className="voicePreview">
                            <button
                              type="button"
                              className="secondary"
                              disabled={
                                !voiceProviderConfigured ||
                                !voiceId ||
                                !greetingValue.trim() ||
                                previewingVoice
                              }
                              onClick={() => void previewVoice()}
                            >
                              {previewingVoice
                                ? "Sintetizando…"
                                : "▶ Ouvir saudação"}
                            </button>
                            {!voiceProviderConfigured && (
                              <small>
                                Configure ELEVENLABS_API_KEY para habilitar
                                catálogo e preview.
                              </small>
                            )}
                            {voicePreviewUrl && (
                              <audio controls autoPlay src={voicePreviewUrl} />
                            )}
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
                                      Record<string, unknown> | undefined
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
                                      Record<string, unknown> | undefined
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
                              value={agentKnowledgeId}
                              onChange={(event) =>
                                setAgentKnowledgeId(event.target.value)
                              }
                            >
                              <option value="">Sem base</option>
                              {knowledge.map((kb) => (
                                <option value={kb.id} key={kb.id}>
                                  {kb.name}
                                </option>
                              ))}
                            </select>
                          </Field>
                          <div className="two">
                            <Field label="Top K da busca">
                              <input
                                name="rag_top_k"
                                type="number"
                                min="1"
                                max="20"
                                defaultValue={String(
                                  (
                                    draft.rag as
                                      Record<string, unknown> | undefined
                                  )?.top_k ?? 5,
                                )}
                              />
                            </Field>
                            <Field label="Score mínimo">
                              <input
                                name="rag_min_score"
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                defaultValue={String(
                                  (
                                    draft.rag as
                                      Record<string, unknown> | undefined
                                  )?.min_score ?? 0.65,
                                )}
                              />
                            </Field>
                          </div>
                          <button
                            type="button"
                            className="secondary"
                            disabled={!agentKnowledgeId}
                            onClick={() => {
                              const kb = knowledge.find(
                                (item) => item.id === agentKnowledgeId,
                              );
                              if (kb) {
                                void openKnowledge(kb).then(() =>
                                  setSection("knowledge"),
                                );
                              }
                            }}
                          >
                            Testar busca
                          </button>
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
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setSection("tools")}
                          >
                            Criar tool
                          </button>
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
                                    Record<string, unknown> | undefined
                                )?.allow_interruptions !== false
                              }
                            />{" "}
                            Permitir interrupções (barge-in)
                          </label>
                        </fieldset>
                        <fieldset
                          className="tabPanel"
                          hidden={agentTab !== "channels"}
                        >
                          <legend>Canais vinculados</legend>
                          {phoneNumbers
                            .filter(
                              (number) =>
                                number.agent_id === selectedAgent.id,
                            )
                            .map((number) => (
                              <div className="row" key={number.id}>
                                <span>
                                  <strong>{String(number.e164)}</strong>
                                  <small>
                                    Telefone · {number.status}
                                  </small>
                                </span>
                              </div>
                            ))}
                          {!phoneNumbers.some(
                            (number) => number.agent_id === selectedAgent.id,
                          ) && <small>Nenhum número vinculado.</small>}
                          <p className="muted">
                            Web widget: disponível na Fase 5. WhatsApp:
                            integração prevista para a Fase 4.
                          </p>
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setSection("numbers")}
                          >
                            Gerenciar números
                          </button>
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
            {section === "live" && (
              <section className="workspace">
                <aside className="list card">
                  <h2>Chamadas em andamento</h2>
                  {calls.filter((call) => ["queued", "ringing", "in_progress"].includes(call.status ?? "")).map((call) => (
                    <div className={`row ${watchedCallId === call.id ? "selected" : ""}`} key={call.id}>
                      <span><strong>{call.channel} Â· {call.status}</strong><small>{call.id}</small></span>
                      <div className="actions">
                        <button type="button" className="secondary" onClick={() => watchLive(call.id)}>Acompanhar</button>
                        <button type="button" onClick={() => void takeoverCall(call)}>Assumir</button>
                      </div>
                    </div>
                  ))}
                  {!calls.some((call) => ["queued", "ringing", "in_progress"].includes(call.status ?? "")) && <Empty>Nenhuma chamada ativa.</Empty>}
                </aside>
                <article className="card editor">
                  <div className="eyebrow">SSE em tempo real</div>
                  <h2>TranscriÃ§Ã£o e eventos</h2>
                  {liveEvents.map((event, index) => (
                    <div className="row" key={index}>
                      <span><strong>{String(event.type ?? "evento")}</strong><small>{JSON.stringify(event.payload ?? event)}</small></span>
                    </div>
                  ))}
                  {!liveEvents.length && <Empty>Selecione “Acompanhar” em uma chamada ativa.</Empty>}
                  {operatorRoom.current && <button type="button" className="danger" onClick={() => { void operatorRoom.current?.disconnect(); operatorRoom.current = null; setNotice("Operador desconectado."); }}>Sair da chamada</button>}
                </article>
              </section>
            )}
            {section === "campaigns" && (
              <section className="workspace">
                <aside className="list card">
                  <h2>Nova campanha</h2>
                  <form onSubmit={createCampaign}>
                    <Field label="Nome"><input name="name" required /></Field>
                    <Field label="Agente">
                      <select name="agent_id" required defaultValue="">
                        <option value="" disabled>Selecione</option>
                        {agents.filter((agent) => agent.status === "active").map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
                      </select>
                    </Field>
                    <Field label="Fuso"><input name="timezone" defaultValue="America/Sao_Paulo" required /></Field>
                    <div className="two">
                      <Field label="InÃ­cio"><input name="start" type="time" defaultValue="08:00" required /></Field>
                      <Field label="Fim"><input name="end" type="time" defaultValue="20:00" required /></Field>
                    </div>
                    <Field label="ConcorrÃªncia"><input name="max_concurrency" type="number" min="1" max="50" defaultValue="2" /></Field>
                    <button>Criar campanha</button>
                  </form>
                </aside>
                <article className="card editor">
                  <div className="eyebrow">discagem em lote</div>
                  <h2>Campanhas</h2>
                  {campaigns.map((campaign) => (
                    <div className="card" key={campaign.id}>
                      <div className="row">
                        <span><strong>{campaign.name}</strong><small>{campaign.status}</small></span>
                      </div>
                      <Field label="Contatos (um por linha: +E164,nome)">
                        <textarea value={campaignContacts[campaign.id] ?? ""} onChange={(event) => setCampaignContacts((items) => ({ ...items, [campaign.id]: event.target.value }))} placeholder="+5511999999999,Ana" />
                      </Field>
                      <div className="actions">
                        <button type="button" className="secondary" disabled={!campaignContacts[campaign.id]?.trim()} onClick={() => void importCampaignContacts(campaign.id, campaignContacts[campaign.id] ?? "")}>Importar</button>
                        {campaign.status === "draft" && <button type="button" onClick={() => void campaignAction(campaign.id, "start")}>Iniciar</button>}
                        {campaign.status === "running" && <button type="button" className="secondary" onClick={() => void campaignAction(campaign.id, "pause")}>Pausar</button>}
                        {campaign.status === "paused" && <button type="button" onClick={() => void campaignAction(campaign.id, "resume")}>Retomar</button>}
                        {["draft", "running", "paused"].includes(campaign.status ?? "") && <button type="button" className="danger" onClick={() => void campaignAction(campaign.id, "cancel")}>Cancelar</button>}
                      </div>
                    </div>
                  ))}
                  {!campaigns.length && <Empty>Nenhuma campanha criada.</Empty>}
                </article>
              </section>
            )}
            {section === "calls" && (
              <section className="workspace">
                <aside className="list card">
                  <h2>Chamadas</h2>
                  <form className="callFilters" onSubmit={filterCalls}>
                    <Field label="Buscar">
                      <input name="q" placeholder="Resumo, telefone ou ID" />
                    </Field>
                    <div className="two">
                      <Field label="Status">
                        <select name="status" defaultValue="">
                          <option value="">Todos</option>
                          <option value="queued">Na fila</option>
                          <option value="ringing">Chamando</option>
                          <option value="in_progress">Em andamento</option>
                          <option value="completed">Concluída</option>
                          <option value="failed">Falhou</option>
                          <option value="cancelled">Cancelada</option>
                        </select>
                      </Field>
                      <Field label="Canal">
                        <select name="channel" defaultValue="">
                          <option value="">Todos</option>
                          <option value="web">Web</option>
                          <option value="phone">Telefone</option>
                          <option value="whatsapp">WhatsApp</option>
                        </select>
                      </Field>
                    </div>
                    <Field label="Agente">
                      <select name="agent_id" defaultValue="">
                        <option value="">Todos</option>
                        {agents.map((agent) => (
                          <option value={agent.id} key={agent.id}>
                            {agent.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <div className="two">
                      <Field label="De">
                        <input name="from" type="date" />
                      </Field>
                      <Field label="Até">
                        <input name="to" type="date" />
                      </Field>
                    </div>
                    <div className="actions">
                      <button>Filtrar</button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={(event) =>
                          void clearCallFilters(event.currentTarget.form!)
                        }
                      >
                        Limpar
                      </button>
                    </div>
                  </form>
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
                      <div className="actions callActions">
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => downloadTranscript(selectedCall)}
                          disabled={!selectedCall.turns?.length}
                        >
                          Baixar transcrição
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => void copyCallId(selectedCall.id)}
                        >
                          Copiar ID
                        </button>
                      </div>
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
                        <details className="toolTest">
                          <summary>Testar</summary>
                          <form
                            className="formGrid"
                            onSubmit={(event) => {
                              event.preventDefault();
                              const form = new FormData(event.currentTarget);
                              const properties = ((
                                tool.parameters_schema as
                                  Record<string, unknown> | undefined
                              )?.properties ?? {}) as Record<
                                string,
                                Record<string, unknown>
                              >;
                              const arguments_ = Object.fromEntries(
                                Object.entries(properties).map(
                                  ([name, schema]) => {
                                    const raw = String(form.get(name) ?? "");
                                    const value =
                                      schema.type === "number" ||
                                      schema.type === "integer"
                                        ? Number(raw)
                                        : schema.type === "boolean"
                                          ? raw === "true"
                                          : raw;
                                    return [name, value];
                                  },
                                ),
                              );
                              void testTool(tool, arguments_);
                            }}
                          >
                            {Object.entries(
                              ((
                                tool.parameters_schema as
                                  Record<string, unknown> | undefined
                              )?.properties ?? {}) as Record<
                                string,
                                Record<string, unknown>
                              >,
                            ).map(([name, schema]) => (
                              <Field
                                key={name}
                                label={String(schema.description ?? name)}
                              >
                                {schema.type === "boolean" ? (
                                  <select name={name} defaultValue="false">
                                    <option value="false">Não</option>
                                    <option value="true">Sim</option>
                                  </select>
                                ) : (
                                  <input
                                    name={name}
                                    type={
                                      schema.type === "number" ||
                                      schema.type === "integer"
                                        ? "number"
                                        : "text"
                                    }
                                    required={(
                                      ((
                                        tool.parameters_schema as Record<
                                          string,
                                          unknown
                                        >
                                      )?.required ?? []) as string[]
                                    ).includes(name)}
                                  />
                                )}
                              </Field>
                            ))}
                            <button className="secondary compact">
                              Testar
                            </button>
                          </form>
                        </details>{" "}
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
                    <div className="two">
                      <Field label="Método HTTP">
                        <select name="method" defaultValue="POST">
                          <option>POST</option>
                          <option>PUT</option>
                          <option>PATCH</option>
                          <option>GET</option>
                          <option>DELETE</option>
                        </select>
                      </Field>
                      <Field label="Timeout (ms)">
                        <input
                          name="timeout_ms"
                          type="number"
                          min="100"
                          max="30000"
                          defaultValue="5000"
                          required
                        />
                      </Field>
                    </div>
                    <Field label="Schema JSON dos parâmetros">
                      <textarea
                        name="parameters_schema"
                        rows={5}
                        defaultValue={JSON.stringify(
                          { type: "object", properties: {}, required: [] },
                          null,
                          2,
                        )}
                        required
                      />
                    </Field>
                    <Field label="Headers JSON">
                      <textarea name="headers" rows={3} defaultValue="{}" />
                    </Field>
                    <div className="two">
                      <Field label="Autenticação">
                        <select name="auth_type" defaultValue="none">
                          <option value="none">Nenhuma</option>
                          <option value="bearer">Bearer</option>
                          <option value="basic">Basic</option>
                          <option value="header">Header</option>
                          <option value="hmac">HMAC</option>
                        </select>
                      </Field>
                      <Field label="Secret">
                        <select name="secret_id" defaultValue="">
                          <option value="">Sem secret</option>
                          {secrets.map((secret) => (
                            <option key={secret.id} value={secret.id}>
                              {secret.name}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                    <Field label="Nome do header de autenticação">
                      <input name="auth_header" defaultValue="X-API-Key" />
                    </Field>
                    <Field label="Body template JSON">
                      <textarea
                        name="body_template"
                        rows={4}
                        defaultValue="{}"
                      />
                    </Field>
                    <Field label="Response mapping JSONPath">
                      <textarea
                        name="response_mapping"
                        rows={3}
                        defaultValue="{}"
                        placeholder={'{"status":"$.status"}'}
                      />
                    </Field>
                    <Field label="Fala antes da execução">
                      <input
                        name="speak_before"
                        placeholder="Vou consultar isso para você."
                      />
                    </Field>
                    <label className="checkRow">
                      <input name="async" type="checkbox" /> Executar sem
                      bloquear a conversa
                    </label>
                    <button>Criar ferramenta</button>
                  </form>
                </article>
              </section>
            )}
            {section === "numbers" && (
              <section className="split">
                <article className="card">
                  <h2>Números da operação</h2>
                  {phoneNumbers.map((number) => (
                    <div className="row static" key={number.id}>
                      <span>
                        <strong>{String(number.e164)}</strong>
                        <small>
                          {String(number.status)} · voz{" "}
                          {String(
                            Boolean(
                              (
                                number.capabilities as
                                  Record<string, unknown> | undefined
                              )?.voice,
                            ),
                          )}{" "}
                          · SMS{" "}
                          {String(
                            Boolean(
                              (
                                number.capabilities as
                                  Record<string, unknown> | undefined
                              )?.sms,
                            ),
                          )}
                        </small>
                      </span>
                      {number.status === "active" && (
                        <span className="actions">
                          <select
                            aria-label={`Agente de ${String(number.e164)}`}
                            value={String(number.agent_id ?? "")}
                            onChange={(event) =>
                              void assignPhoneNumber(
                                number.id,
                                event.target.value,
                              )
                            }
                          >
                            <option value="">Sem agente</option>
                            {agents
                              .filter((agent) => agent.status === "active")
                              .map((agent) => (
                                <option key={agent.id} value={agent.id}>
                                  {agent.name}
                                </option>
                              ))}
                          </select>
                          <button
                            type="button"
                            className="danger compact"
                            onClick={() => void releasePhoneNumber(number.id)}
                          >
                            Liberar
                          </button>
                        </span>
                      )}
                    </div>
                  ))}
                  {!phoneNumbers.length && (
                    <Empty>Nenhum número comprado neste workspace.</Empty>
                  )}
                </article>
                <article className="card">
                  <h2>Comprar número BR</h2>
                  <form className="formGrid" onSubmit={searchPhoneNumbers}>
                    <Field label="DDD">
                      <input
                        name="area_code"
                        inputMode="numeric"
                        pattern="[0-9]{2,3}"
                        defaultValue="11"
                        required
                      />
                    </Field>
                    <button>Buscar no Twilio</button>
                  </form>
                  {availableNumbers.map((number) => (
                    <div className="row static" key={number.e164}>
                      <span>
                        <strong>{number.friendly_name ?? number.e164}</strong>
                        <small>
                          {[number.locality, number.region]
                            .filter(Boolean)
                            .join(" · ") || "Brasil"}
                        </small>
                      </span>
                      <button
                        type="button"
                        className="compact"
                        onClick={() => void purchasePhoneNumber(number.e164)}
                      >
                        Comprar
                      </button>
                    </div>
                  ))}
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
                      <span className="actions">
                        <select
                          aria-label={`Papel de ${String(member.email)}`}
                          defaultValue={String(member.role)}
                          disabled={member.role === "owner" && ownerCount === 1}
                          title={
                            member.role === "owner" && ownerCount === 1
                              ? "Promova outro owner antes de alterar este papel"
                              : undefined
                          }
                          onChange={(event) =>
                            void updateMember(member.id, event.target.value)
                          }
                        >
                          <option value="viewer">Viewer</option>
                          <option value="operator">Operator</option>
                          <option value="developer">Developer</option>
                          <option value="admin">Admin</option>
                          <option value="owner">Owner</option>
                        </select>
                        <button
                          className="danger"
                          type="button"
                          disabled={member.role === "owner" && ownerCount === 1}
                          title={
                            member.role === "owner" && ownerCount === 1
                              ? "O workspace precisa manter ao menos um owner"
                              : undefined
                          }
                          onClick={() => void removeMember(member.id)}
                        >
                          Remover
                        </button>
                      </span>
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
            {section === "billing" && billingPlan && billingUsage && (
              <>
                <section className="stats">
                  <article className="card"><span className="muted">Plano</span><strong className="value">{billingPlan.name}</strong></article>
                  <article className="card"><span className="muted">Minutos usados</span><strong className="value">{billingUsage.minutes}</strong></article>
                  <article className="card"><span className="muted">Incluídos</span><strong className="value">{billingUsage.included_minutes}</strong></article>
                  <article className="card"><span className="muted">Excedente estimado</span><strong className="value">{(billingUsage.estimated_overage_cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</strong></article>
                </section>
                <section className="split">
                  <article className="card">
                    <h2>Assinatura</h2>
                    <p>Plano atual: <b>{billingPlan.code}</b> · {billingPlan.subscription_status ?? "trial"}</p>
                    <div className="actions">
                      {billingPlan.code !== "starter" && <button type="button" onClick={() => void upgradePlan("starter")}>Starter · R$ 297</button>}
                      {billingPlan.code !== "pro" && <button type="button" onClick={() => void upgradePlan("pro")}>Pro · R$ 897</button>}
                      {billingPlan.code !== "business" && <button type="button" onClick={() => void upgradePlan("business")}>Business · R$ 2.497</button>}
                      <button type="button" className="secondary" onClick={() => void openBillingPortal()}>Portal e cartão</button>
                    </div>
                  </article>
                  <article className="card">
                    <h2>Faturas</h2>
                    {invoices.map((invoice) => (
                      <div className="row" key={invoice.id}><span><strong>{String(invoice.status)}</strong><small>{(Number(invoice.amount_cents ?? 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</small></span>{typeof invoice.pdf_url === "string" && invoice.pdf_url && <a href={invoice.pdf_url} target="_blank" rel="noreferrer">PDF</a>}</div>
                    ))}
                    {!invoices.length && <Empty>Nenhuma fatura emitida.</Empty>}
                  </article>
                </section>
              </>
            )}
            {section === "settings" && (
              <section className="split">
                <article className="card">
                  <h2>Geral</h2>
                  <form className="formGrid" onSubmit={updateTenant}>
                    <Field label="Nome do workspace">
                      <input name="name" required defaultValue={tenant?.name} />
                    </Field>
                    <Field label="Fuso horário">
                      <input
                        name="timezone"
                        required
                        defaultValue={String(
                          (tenant?.settings as Record<string, unknown>)
                            ?.timezone ?? "America/Sao_Paulo",
                        )}
                      />
                    </Field>
                    <Field label="Retenção das gravações (dias)">
                      <input
                        name="retention_days"
                        type="number"
                        min="1"
                        max="3650"
                        required
                        defaultValue={Number(
                          (tenant?.settings as Record<string, unknown>)
                            ?.retention_days ?? 90,
                        )}
                      />
                    </Field>
                    <label className="checkRow">
                      <input
                        name="recording_enabled"
                        type="checkbox"
                        defaultChecked={Boolean(
                          (tenant?.settings as Record<string, unknown>)
                            ?.recording_enabled ?? true,
                        )}
                      />
                      Gravar chamadas
                    </label>
                    <button>Salvar configurações</button>
                  </form>
                  <hr />
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
                  <h2>Secrets de integrações</h2>
                  <p className="muted">
                    Valores são criptografados e nunca retornam pela API.
                  </p>
                  <form className="formGrid" onSubmit={createSecret}>
                    <Field label="Nome">
                      <input name="name" required placeholder="crm_api_key" />
                    </Field>
                    <Field label="Valor secreto">
                      <input name="value" type="password" required />
                    </Field>
                    <button>Salvar secret</button>
                  </form>
                  {secrets.map((secret) => (
                    <div className="row static" key={secret.id}>
                      <span>
                        <strong>{secret.name}</strong>
                        <small>valor protegido</small>
                      </span>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => void deleteSecret(secret.id)}
                      >
                        Remover
                      </button>
                    </div>
                  ))}
                  <h2>Chaves existentes</h2>
                  {apiKeys.map((key) => (
                    <div className="row static" key={key.id}>
                      <span>
                        <strong>{key.name}</strong>
                        <small>
                          {String(key.prefix)}… · {String(key.scope)}
                        </small>
                      </span>
                      <span className="actions">
                        <span className={`pill ${key.revoked_at ? "" : "ok"}`}>
                          {key.revoked_at ? "revogada" : "ativa"}
                        </span>
                        {!key.revoked_at && (
                          <button
                            className="danger"
                            type="button"
                            onClick={() => void revokeApiKey(key.id)}
                          >
                            Revogar
                          </button>
                        )}
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
