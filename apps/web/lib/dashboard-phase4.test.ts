import { describe, expect, it } from "vitest";

import {
  buildSimulationCreatePayload,
  buildWhatsappConnectPayload,
  buildWhatsappHandoffRequest,
  findWhatsappIntegration,
  simulationReportMetrics,
  simulationYamlPath,
} from "./dashboard-phase4";

describe("dashboard phase 4 helpers", () => {
  it("selects the WhatsApp integration deterministically", () => {
    expect(
      findWhatsappIntegration([
        { id: "google-1", provider: "google" },
        {
          id: "wa-1",
          provider: "whatsapp",
          config: { phone_number_id: "phone-123" },
        },
      ]),
    ).toEqual({
      id: "wa-1",
      provider: "whatsapp",
      config: { phone_number_id: "phone-123" },
    });
  });

  it("builds the WhatsApp connect payload from form data", () => {
    const form = new FormData();
    form.set("phone_number_id", "phone-123");
    form.set("business_account_id", "waba-123");
    form.set("access_token", "token-xyz");
    form.set("agent_id", "agent-123");

    expect(buildWhatsappConnectPayload(form)).toEqual({
      phone_number_id: "phone-123",
      business_account_id: "waba-123",
      access_token: "token-xyz",
      agent_id: "agent-123",
    });
  });

  it("rejects empty WhatsApp handoff requests and trims valid text", () => {
    expect(buildWhatsappHandoffRequest(null, "Oi")).toBeNull();
    expect(buildWhatsappHandoffRequest("call-1", "   ")).toBeNull();
    expect(buildWhatsappHandoffRequest("call-1", "  Operador assumiu.  ")).toEqual({
      path: "calls/call-1/whatsapp-handoff",
      body: { text: "Operador assumiu." },
    });
  });

  it("builds the simulator payload and YAML path", () => {
    const form = new FormData();
    form.set("agent_id", "agent-456");
    form.set("persona", "Paciente com dúvidas recorrentes.");
    form.set("objective", "Validar clareza.");
    form.set("conversation_count", "20");

    expect(buildSimulationCreatePayload(form)).toEqual({
      agent_id: "agent-456",
      persona: "Paciente com dúvidas recorrentes.",
      objective: "Validar clareza.",
      conversation_count: 20,
    });
    expect(simulationYamlPath("sim-123")).toBe("/api/voiceos/simulations/sim-123/yaml");
  });

  it("formats simulation report metrics with deterministic fallbacks", () => {
    expect(
      simulationReportMetrics({
        id: "sim-123",
        conversation_count: 20,
        report: { conversation_count: 20, average_score: 92, pass_rate: 0.95 },
      }),
    ).toEqual({
      conversationCount: "20",
      averageScore: "92",
      passRate: "0.95",
    });

    expect(simulationReportMetrics({ id: "sim-456" })).toEqual({
      conversationCount: "—",
      averageScore: "—",
      passRate: "—",
    });
  });
});
