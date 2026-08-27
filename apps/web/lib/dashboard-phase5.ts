type BrandingSettings = {
  product_name?: string;
  logo_url?: string;
  favicon_url?: string;
  primary_color?: string;
  accent_color?: string;
  email_from_name?: string;
  custom_domain?: string;
};

type WidgetSettings = {
  button_label?: string;
  theme?: "light" | "dark" | "system";
  position?: "bottom-right" | "bottom-left";
  livekit_module_url?: string;
};

export function buildTenantSettingsPayload(form: FormData): {
  name: FormDataEntryValue | null;
  settings: {
    timezone: FormDataEntryValue | null;
    recording_enabled: boolean;
    retention_days: number;
    anonymize_transcripts: boolean;
    branding: BrandingSettings;
    widget: WidgetSettings;
  };
} {
  return {
    name: form.get("name"),
    settings: {
      timezone: form.get("timezone"),
      recording_enabled: form.get("recording_enabled") === "on",
      retention_days: Number(form.get("retention_days")),
      anonymize_transcripts: form.get("anonymize_transcripts") === "on",
      branding: compactObject({
        product_name: stringOrUndefined(form.get("product_name")),
        logo_url: stringOrUndefined(form.get("logo_url")),
        favicon_url: stringOrUndefined(form.get("favicon_url")),
        primary_color: stringOrUndefined(form.get("primary_color")),
        accent_color: stringOrUndefined(form.get("accent_color")),
        email_from_name: stringOrUndefined(form.get("email_from_name")),
        custom_domain: stringOrUndefined(form.get("custom_domain")),
      }),
      widget: compactObject({
        button_label: stringOrUndefined(form.get("widget_button_label")),
        theme: widgetTheme(form.get("widget_theme")),
        position: widgetPosition(form.get("widget_position")),
        livekit_module_url: stringOrUndefined(form.get("widget_livekit_module_url")),
      }),
    },
  };
}

export function buildWidgetScriptSnippet(options: {
  tenantId: string;
  agentId: string;
  publicKey: string;
  hostOrigin: string;
  buttonLabel?: string;
  theme?: string;
  position?: string;
  livekitModuleUrl?: string;
}): string {
  const lines = [
    `<script type="module" src="${options.hostOrigin}/voiceos.js"`,
    `  data-agent-id="${options.agentId}"`,
    `  data-key="${options.publicKey}"`,
    `  data-api-url="${options.hostOrigin}/v1/public/tenants/${options.tenantId}/widget/sessions"`,
  ];
  if (options.buttonLabel) {
    lines.push(`  data-button-label="${options.buttonLabel}"`);
  }
  if (options.theme) {
    lines.push(`  data-theme="${options.theme}"`);
  }
  if (options.position) {
    lines.push(`  data-position="${options.position}"`);
  }
  if (options.livekitModuleUrl) {
    lines.push(`  data-livekit-module-url="${options.livekitModuleUrl}"`);
  }
  lines.push(`></script>`);
  return lines.join("\n");
}

export function buildWidgetReactSnippet(options: {
  tenantId: string;
  agentId: string;
  publicKey: string;
  hostOrigin: string;
  buttonLabel?: string;
  theme?: string;
  position?: string;
  livekitModuleUrl?: string;
}): string {
  const lines = [
    'import { VoiceOSWidget } from "@voiceos/web";',
    "",
    "const widget = new VoiceOSWidget({",
    `  agentId: "${options.agentId}",`,
    `  publicKey: "${options.publicKey}",`,
    `  apiUrl: "${options.hostOrigin}/v1/public/tenants/${options.tenantId}/widget/sessions",`,
    `  buttonLabel: "${options.buttonLabel ?? "Falar agora"}",`,
    `  theme: "${options.theme ?? "system"}",`,
    `  position: "${options.position ?? "bottom-right"}",`,
  ];
  if (options.livekitModuleUrl) {
    lines.push(`  livekitModuleUrl: "${options.livekitModuleUrl}",`);
  }
  lines.push("});", "widget.mount();");
  return lines.join("\n");
}

function compactObject<T extends Record<string, unknown>>(value: T): T {
  return Object.fromEntries(
    Object.entries(value).filter(([, candidate]) => candidate !== undefined && candidate !== ""),
  ) as T;
}

function stringOrUndefined(value: FormDataEntryValue | null): string | undefined {
  const trimmed = String(value ?? "").trim();
  return trimmed || undefined;
}

function widgetTheme(value: FormDataEntryValue | null): WidgetSettings["theme"] {
  const candidate = String(value ?? "").trim();
  return candidate === "light" || candidate === "dark" || candidate === "system"
    ? candidate
    : undefined;
}

function widgetPosition(value: FormDataEntryValue | null): WidgetSettings["position"] {
  const candidate = String(value ?? "").trim();
  return candidate === "bottom-left" || candidate === "bottom-right"
    ? candidate
    : undefined;
}
