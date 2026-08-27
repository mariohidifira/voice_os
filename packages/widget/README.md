# @voiceos/web

Embeddable VoiceOS widget for HTML, React, and Next.js hosts.

The browser bundle is generated as `packages/widget/dist/voiceos.js` and synchronized to
`apps/web/public/voiceos.js` during `npm run build --workspace=@voiceos/web` and before
`npm run build --workspace=@voiceos/dashboard`.

## HTML

```html
<script
  type="module"
  src="https://app.voiceos.example/voiceos.js"
  data-agent-id="agent_123"
  data-key="vos_pk_..."
  data-api-url="https://app.voiceos.example/v1/public/tenants/<tenant_id>/widget/sessions"
  data-button-label="Falar agora"
  data-theme="system"
  data-position="bottom-right"
  data-livekit-module-url="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.esm.mjs"
></script>
```

## React / Next.js

```ts
import { VoiceOSWidget } from "@voiceos/web";

const widget = new VoiceOSWidget({
  agentId: "agent_123",
  publicKey: "vos_pk_...",
  apiUrl: "https://app.voiceos.example/v1/public/tenants/<tenant_id>/widget/sessions",
  buttonLabel: "Falar agora",
  theme: "system",
  position: "bottom-right",
  livekitModuleUrl: "https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.esm.mjs",
});

widget.mount();
```

The widget loads the LiveKit browser module dynamically from jsDelivr by default. If you need a pinned or self-hosted asset, pass `livekitModuleUrl`.

## Events

- `voiceos:start`
- `voiceos:end`

```ts
window.addEventListener("voiceos:start", (event) => {
  console.log("widget opened", event);
});
```

## Local host example

Use `packages/widget/examples/host-page.html` as a minimal static host to validate the auto-bootstrap flow against `../dist/voiceos.js`.

For hosted embeds, `apiUrl` should point to `.../v1/public/tenants/<tenant_id>/widget/sessions`.

## Size budget

The browser bundle is constrained to `<= 60 KB` gzipped. Run:

```bash
npm run build --workspace=@voiceos/web
npm run size --workspace=@voiceos/web
```

The build writes `packages/widget/dist/size.json` with the current raw and gzipped sizes.
