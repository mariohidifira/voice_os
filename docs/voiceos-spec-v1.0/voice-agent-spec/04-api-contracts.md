# 04 — Contratos de API

Base: `https://api.voiceos.example`. JSON. Versionamento no path (`/v1`). OpenAPI 3.1 gerada pelo FastAPI em `/openapi.json`; tipos TS gerados por `openapi-typescript` em `packages/shared-ts` no build.

## Autenticação

| Contexto | Mecanismo | Header |
|---|---|---|
| Painel (`web` → `api`) | JWT emitido pelo Auth.js (RS256), contém `sub`, `email`, `tenants[]` | `Authorization: Bearer <jwt>` + `X-Tenant-Id: <uuid>` |
| API pública servidor-a-servidor | API key `secret` (`vk_live_...`) | `Authorization: Bearer vk_live_...` |
| Widget/browser | API key `public` (`vk_pub_...`) + allowlist de origem; só pode criar sessão | `Authorization: Bearer vk_pub_...` |
| Interno | `X-Internal-Token` | só na VPC |
| Webhooks de terceiros | assinatura própria de cada provedor (Twilio `X-Twilio-Signature`, Stripe `Stripe-Signature`, Meta `X-Hub-Signature-256`) | |

Autorização por role (`08-painel-multitenant.md` tem a matriz). Toda rota declara `required_role`.

## Formato de erro
```json
{ "error": { "code": "agent_not_found", "message": "Agent not found", "details": {}, "request_id": "req_..." } }
```
HTTP: 400 validação (`validation_error`), 401 `unauthenticated`, 403 `forbidden`, 404 `*_not_found`, 409 `conflict`, 422 `unprocessable`, 429 `rate_limited`, 500 `internal`, 503 `provider_unavailable`.

Paginação: cursor. Query `?limit=50&cursor=...`; resposta `{ "data": [...], "next_cursor": "..." | null }`. Ordenação default `created_at desc`.

Idempotência: rotas POST que criam efeitos (sessions, calls outbound, campaigns) aceitam `Idempotency-Key`; guardar 24 h no Redis.

Rate limit: 600 req/min por API key; 60 req/min para `POST /v1/sessions` por origem. Header `Retry-After`.

## Endpoints

### Auth / conta
- `GET /v1/me` → usuário, memberships, tenant atual
- `POST /v1/tenants` (platform admin) → cria tenant + owner
- `GET /v1/tenants/{id}` · `PATCH /v1/tenants/{id}` (settings)
- `GET /v1/tenants/{id}/members` · `POST .../members` (convite por e-mail) · `PATCH .../members/{user_id}` (role) · `DELETE`

### Agents
- `GET /v1/agents` · `POST /v1/agents` `{name}` → cria agent + draft version com defaults
- `GET /v1/agents/{id}` → agent + draft + current
- `PATCH /v1/agents/{id}` `{name,status}`
- `GET /v1/agents/{id}/versions` · `GET .../versions/{vid}`
- `PATCH /v1/agents/{id}/draft` → atualiza campos do draft (partial)
- `POST /v1/agents/{id}/publish` → congela draft como nova versão, define `current_version_id`, cria novo draft cópia. Invalida cache runtime.
- `POST /v1/agents/{id}/rollback` `{version_id}`
- `POST /v1/agents/{id}/test-session` → sessão WebRTC usando o **draft** (para testar antes de publicar)
- `DELETE /v1/agents/{id}` (soft)

### Tools
- `GET /v1/tools` · `POST /v1/tools` · `GET/PATCH/DELETE /v1/tools/{id}`
- `POST /v1/tools/{id}/test` `{arguments}` → executa webhook e retorna resposta bruta + mapeada (para depurar)
- `PUT /v1/agents/{id}/draft/tools` `{tool_ids: []}` → define set de tools do draft

### Knowledge base
- `GET /v1/knowledge-bases` · `POST` · `GET/PATCH/DELETE /{id}`
- `POST /v1/knowledge-bases/{id}/documents` multipart (`file`) ou `{url}` ou `{text, name}` → 202, job de ingestão
- `GET /v1/knowledge-bases/{id}/documents` · `DELETE .../documents/{doc_id}`
- `POST /v1/knowledge-bases/{id}/query` `{query, top_k}` → chunks com score (debug)

### Phone numbers
- `GET /v1/phone-numbers/available?country=BR&area_code=11` → busca no Twilio
- `POST /v1/phone-numbers` `{e164}` → compra, configura SIP trunk, cria dispatch rule
- `PATCH /v1/phone-numbers/{id}` `{agent_id}` → reatribui
- `DELETE /v1/phone-numbers/{id}` → libera

### Sessions (WebRTC)
- `POST /v1/sessions` `{agent_id, end_user?: {external_id, name, phone, email, metadata}, variables?: {}, metadata?: {}}` → `{session_id, call_id, livekit_url, token, expires_at}`
  - Valida `agent.status = active` e origem (se key pública)
  - Se `end_user` vier, upsert em `end_users`
- `DELETE /v1/sessions/{id}` → encerra

### Calls
- `GET /v1/calls?agent_id&channel&status&from&to&end_user_id&q` (q busca em summary/transcrição via `tsvector`)
- `GET /v1/calls/{id}` → call + turns + tool_calls + events + recording url assinada (15 min) + qa
- `GET /v1/calls/{id}/live` → SSE de eventos em tempo real (`turn.user`, `turn.agent`, `tool.called`, ...)
- `POST /v1/calls/{id}/hangup`
- `POST /v1/calls/{id}/transfer` `{to}` (operator+)
- `POST /v1/calls/outbound` `{agent_id, to, variables?, end_user?, metadata?}` → 202 `{call_id}`; agente liga

### Campaigns
- `GET/POST /v1/campaigns` · `GET/PATCH /v1/campaigns/{id}`
- `POST /v1/campaigns/{id}/contacts` (JSON array ou CSV multipart) · `GET .../contacts?status`
- `POST /v1/campaigns/{id}/start` · `.../pause` · `.../resume` · `.../cancel`

### End users
- `GET /v1/end-users?q` · `GET /v1/end-users/{id}` (+ últimas calls) · `PATCH` · `DELETE` (LGPD: anonimiza calls vinculadas)

### API keys e webhooks
- `GET/POST /v1/api-keys` (retorna a chave só na criação) · `DELETE /v1/api-keys/{id}`
- `GET/POST/PATCH/DELETE /v1/webhooks` · `GET /v1/webhooks/{id}/deliveries` · `POST .../deliveries/{did}/retry`

### Billing
- `GET /v1/billing/plan` · `POST /v1/billing/checkout` `{plan_code}` → Stripe Checkout URL · `POST /v1/billing/portal` → Stripe Portal URL
- `GET /v1/billing/usage?period=2026-08` → minutos usados/incluídos/excedentes, custo estimado
- `GET /v1/billing/invoices`

### Analytics
- `GET /v1/analytics/overview?from&to&agent_id` → `{calls, minutes, avg_duration, resolution_rate, transfer_rate, abandon_rate, csat, latency_p50, latency_p95, cost}` + série diária
- `GET /v1/analytics/tools?from&to` → uso e erro por tool

### Exports (LGPD / dados)
- `POST /v1/exports` `{type: "calls"|"end_user", filters}` → 202; job gera CSV/JSON no S3; e-mail com link
- `GET /v1/exports/{id}`

### Admin (platform admin, `/admin/*`)
- `GET /admin/tenants` · `PATCH /admin/tenants/{id}` (plan, status) · `POST /admin/tenants/{id}/impersonate` (JWT curto, auditado)
- `GET /admin/metrics` (uso global, custo por provedor, salas ativas)

### Internos (`/internal/*`)
- `GET /internal/agents/{id}/runtime?version=current|draft|<id>` → config resolvida para o agent-worker: prompt renderizado parcialmente, tools com schema, segredos descriptografados só dos webhooks, config stt/tts/llm, KB id
- `POST /internal/calls` (cria registro ao entrar na room) · `PATCH /internal/calls/{id}` (status, timestamps)
- `POST /internal/calls/{id}/events` (batch) · `POST /internal/calls/{id}/turns` (batch) · `POST /internal/calls/{id}/tool-calls`
- `POST /internal/rag/query` `{knowledge_base_id, query, top_k, min_score}` → chunks
- `POST /internal/tools/execute` `{tool_id, arguments, call_id}` → executa webhook do lado da API (mantém segredos fora do agent-worker)

### Webhooks recebidos
- `POST /webhooks/twilio/voice-status` (status callback) · `POST /webhooks/twilio/sms-status`
- `POST /webhooks/livekit` (room started/finished, egress ended, sip events)
- `POST /webhooks/stripe`
- `GET/POST /webhooks/whatsapp`
Todos validam assinatura e respondem 200 rápido; processamento vai para fila.

## Webhooks enviados ao tenant
Eventos: `call.started`, `call.ended`, `call.transferred`, `tool.failed`, `campaign.finished`, `document.ready`, `document.error`, `usage.threshold` (80%, 100%).
Payload:
```json
{ "id": "evt_...", "type": "call.ended", "created_at": "...", "tenant_id": "...", "data": { "call": { ...call sem turns... , "summary": "...", "outcome": {...}, "variables": {...}, "recording_url": "..." } } }
```
Header `X-VoiceOS-Signature: t=<ts>,v1=<hmac_sha256(secret, ts + "." + body)>`. Retry exponencial: 1 min, 5, 30, 2 h, 12 h (5 tentativas). Timeout 10 s.
