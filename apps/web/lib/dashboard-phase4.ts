type Item = Record<string, unknown> & {
  id: string;
  name?: string;
  status?: string;
};

type Integration = Item & {
  provider: string;
  account_email?: string;
  config?: Record<string, unknown>;
};

type Simulation = Item & {
  agent_id?: string;
  persona?: string;
  objective?: string;
  conversation_count?: number;
  report?: Record<string, unknown>;
};

export function findWhatsappIntegration(
  integrations: Integration[],
): Integration | undefined {
  return integrations.find((integration) => integration.provider === "whatsapp");
}

export function buildWhatsappConnectPayload(form: FormData): {
  phone_number_id: FormDataEntryValue | null;
  business_account_id: FormDataEntryValue | null;
  access_token: FormDataEntryValue | null;
  agent_id: FormDataEntryValue | null;
} {
  return {
    phone_number_id: form.get("phone_number_id"),
    business_account_id: form.get("business_account_id"),
    access_token: form.get("access_token"),
    agent_id: form.get("agent_id"),
  };
}

export function buildWhatsappHandoffRequest(
  watchedCallId: string | null,
  text: string,
): { path: string; body: { text: string } } | null {
  const trimmed = text.trim();
  if (!watchedCallId || !trimmed) {
    return null;
  }
  return {
    path: `calls/${watchedCallId}/whatsapp-handoff`,
    body: { text: trimmed },
  };
}

export function buildSimulationCreatePayload(form: FormData): {
  agent_id: FormDataEntryValue | null;
  persona: FormDataEntryValue | null;
  objective: FormDataEntryValue | null;
  conversation_count: number;
} {
  return {
    agent_id: form.get("agent_id"),
    persona: form.get("persona"),
    objective: form.get("objective"),
    conversation_count: Number(form.get("conversation_count")),
  };
}

export function simulationYamlPath(simulationId: string): string {
  return `/api/voiceos/simulations/${simulationId}/yaml`;
}

export function simulationReportMetrics(simulation: Simulation): {
  conversationCount: string;
  averageScore: string;
  passRate: string;
} {
  return {
    conversationCount: String(
      simulation.report?.conversation_count ?? simulation.conversation_count ?? "—",
    ),
    averageScore: String(simulation.report?.average_score ?? "—"),
    passRate: String(simulation.report?.pass_rate ?? "—"),
  };
}
