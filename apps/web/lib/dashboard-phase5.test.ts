import { describe, expect, it } from "vitest";

import {
  buildTenantSettingsPayload,
  buildWidgetReactSnippet,
  buildWidgetScriptSnippet,
} from "./dashboard-phase5";

describe("dashboard phase 5 helpers", () => {
  it("builds the tenant settings payload with branding and widget settings", () => {
    const form = new FormData();
    form.set("name", "VoiceOS White Label");
    form.set("timezone", "America/Sao_Paulo");
    form.set("retention_days", "120");
    form.set("recording_enabled", "on");
    form.set("product_name", "Clínica Aurora");
    form.set("primary_color", "#123456");
    form.set("accent_color", "#abcdef");
    form.set("widget_button_label", "Falar com a clínica");
    form.set("widget_theme", "dark");
    form.set("widget_position", "bottom-left");
    form.set("widget_livekit_module_url", "https://cdn.example.com/livekit.esm.js");

    expect(buildTenantSettingsPayload(form)).toEqual({
      name: "VoiceOS White Label",
      settings: {
        timezone: "America/Sao_Paulo",
        recording_enabled: true,
        retention_days: 120,
        anonymize_transcripts: false,
        branding: {
          product_name: "Clínica Aurora",
          primary_color: "#123456",
          accent_color: "#abcdef",
        },
        widget: {
          button_label: "Falar com a clínica",
          theme: "dark",
          position: "bottom-left",
          livekit_module_url: "https://cdn.example.com/livekit.esm.js",
        },
      },
    });
  });

  it("builds deterministic widget snippets", () => {
    expect(
      buildWidgetScriptSnippet({
        tenantId: "tenant-abc",
        agentId: "agent-123",
        publicKey: "vos_pk_demo",
        hostOrigin: "https://voice.example.com",
      }),
    ).toContain(`src="https://voice.example.com/voiceos.js"`);
    expect(
      buildWidgetScriptSnippet({
        tenantId: "tenant-abc",
        agentId: "agent-123",
        publicKey: "vos_pk_demo",
        hostOrigin: "https://voice.example.com",
        buttonLabel: "Falar agora",
        theme: "light",
        position: "bottom-right",
        livekitModuleUrl: "https://cdn.example.com/livekit.esm.js",
      }),
    ).toContain(`data-agent-id="agent-123"`);
    expect(
      buildWidgetScriptSnippet({
        tenantId: "tenant-abc",
        agentId: "agent-123",
        publicKey: "vos_pk_demo",
        hostOrigin: "https://voice.example.com",
        livekitModuleUrl: "https://cdn.example.com/livekit.esm.js",
      }),
    ).toContain(`data-livekit-module-url="https://cdn.example.com/livekit.esm.js"`);
    expect(
      buildWidgetScriptSnippet({
        tenantId: "tenant-abc",
        agentId: "agent-123",
        publicKey: "vos_pk_demo",
        hostOrigin: "https://voice.example.com",
      }),
    ).toContain(`/v1/public/tenants/tenant-abc/widget/sessions`);

    expect(
      buildWidgetReactSnippet({
        tenantId: "tenant-abc",
        agentId: "agent-123",
        publicKey: "vos_pk_demo",
        hostOrigin: "https://voice.example.com",
        livekitModuleUrl: "https://cdn.example.com/livekit.esm.js",
      }),
    ).toContain(`livekitModuleUrl: "https://cdn.example.com/livekit.esm.js"`);
  });
});
