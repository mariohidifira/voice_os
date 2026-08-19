# 02 — Arquitetura

## Visão geral

```
                    ┌────────────────────────────────────────────────────────┐
                    │                      Canais                            │
                    │  Browser/App (WebRTC)   Telefone (PSTN→Twilio SIP)     │
                    │  WhatsApp (Cloud API webhook)                          │
                    └──────────┬───────────────────┬─────────────────┬───────┘
                               │                   │                 │
                        ┌──────▼──────┐    ┌───────▼──────┐   ┌──────▼──────────┐
                        │ LiveKit     │    │ LiveKit SIP  │   │ whatsapp-worker │
                        │ Cloud (SFU) │◄───┤ (trunk in/out)│   │ (async pipeline)│
                        └──────┬──────┘    └──────────────┘   └──────┬──────────┘
                               │ room join                            │
                    ┌──────────▼───────────────────────────────────────▼─────┐
                    │                agent-worker (Python)                    │
                    │  LiveKit Agents: VAD → STT → LLM(+tools) → TTS          │
                    │  Barge-in, turn detection, RAG, tool executor           │
                    └──────────┬───────────────────────────┬─────────────────┘
                               │ REST/gRPC interno         │ eventos
                    ┌──────────▼──────────┐       ┌────────▼────────┐
                    │  api (FastAPI)      │◄──────┤  Redis           │
                    │  painel, tenants,   │       │  pub/sub, cache, │
                    │  agents, tools,     │       │  rate limit      │
                    │  calls, billing,    │       └──────────────────┘
                    │  webhooks Twilio/   │
                    │  Stripe/WhatsApp    │
                    └──────────┬──────────┘
                    ┌──────────▼──────────┐   ┌──────────────┐  ┌──────────┐
                    │  PostgreSQL 16      │   │  S3          │  │ worker   │
                    │  + pgvector         │   │  gravações,  │  │ (jobs:   │
                    │  RLS por tenant     │   │  docs, exports│  │ ingest,  │
                    └─────────────────────┘   └──────────────┘  │ QA, bill)│
                                                                └──────────┘
                    ┌─────────────────────┐
                    │  web (Next.js)      │  → painel multi-tenant + widget
                    └─────────────────────┘

Provedores externos: Deepgram (STT) · Anthropic (LLM) · ElevenLabs (TTS) ·
Twilio (SIP/PSTN/SMS) · Meta (WhatsApp) · Stripe (billing) · Resend (e-mail)
```

## Componentes

| Componente | Tecnologia | Responsabilidade | Escala |
|---|---|---|---|
| `web` | Next.js 15, TS, Tailwind, shadcn/ui, Auth.js | Painel, widget embutível, landing | Vercel ou ECS; stateless |
| `api` | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 | REST API, auth JWT, webhooks de terceiros, orquestração de chamadas outbound | ECS Fargate, 2+ tasks, ALB |
| `agent-worker` | LiveKit Agents SDK (Python), plugins deepgram/anthropic/elevenlabs/silero | Executa o pipeline de voz por sala; um processo atende N salas (default 10) | ECS Fargate, autoscale por salas ativas |
| `worker` | Python + `arq` (Redis) | Jobs assíncronos: ingestão de documentos, embeddings, pós-processamento de chamada, QA por LLM, medição de billing, exports | ECS Fargate |
| `whatsapp-worker` | Python (parte do `worker`) | Recebe webhook, baixa áudio, roda STT → LLM → TTS não-streaming, responde | idem |
| `db` | PostgreSQL 16 + pgvector | Dados + vetores | RDS Multi-AZ |
| `redis` | Redis 7 | Cache, sessões, filas `arq`, pub/sub de eventos ao vivo, rate limit | ElastiCache |
| `s3` | AWS S3 | `voiceos-recordings`, `voiceos-documents`, `voiceos-exports` | — |
| LiveKit Cloud | SaaS | SFU WebRTC, SIP ingress/egress, egress de gravação | — |

## Fluxo de dados: chamada inbound telefone (resumo)

1. Twilio recebe chamada no número → SIP INVITE para LiveKit SIP trunk.
2. LiveKit aplica `dispatch rule` (por número chamado) → cria room `call_<uuid>` com metadata `{tenant_id, agent_id, channel: "phone", from, to}`.
3. `agent-worker` recebe job de dispatch, carrega config do agente da API (`GET /internal/agents/{id}/runtime`, cacheado no Redis por 60 s), instancia pipeline e entra na room.
4. Agente fala saudação (`greeting`), pipeline roda (`05-voice-pipeline.md`).
5. Eventos (`call.started`, `turn.user`, `turn.agent`, `tool.called`, `call.ended`) são publicados no Redis e persistidos via `POST /internal/calls/{id}/events` em lote a cada 2 s.
6. Ao encerrar: egress de gravação vai para S3; `worker` roda pós-processamento (transcrição final consolidada, resumo, QA, custo, minutos para billing) e dispara webhook do tenant se configurado.

## Fluxo: WebRTC (web/app)
1. Frontend chama `POST /v1/sessions` com `agent_id` (+ `end_user` opcional com dados do usuário logado) usando API key pública do tenant → API valida origem (allowlist de domínios), cria room, gera token LiveKit com TTL 1 h e metadata.
2. Cliente conecta na room via LiveKit JS SDK. Dispatch igual ao telefone.

## Fluxo: WhatsApp
Ver `09-canais.md`. Não é tempo real; passa por `worker` com pipeline não-streaming.

## Repositório (monorepo)

```
voiceos/
  apps/
    web/                 Next.js
    api/                 FastAPI
    agent-worker/        LiveKit Agents
    worker/              arq jobs (inclui whatsapp)
  packages/
    shared-py/           modelos Pydantic compartilhados, clients, tool schemas
    shared-ts/           tipos gerados da OpenAPI, SDK do widget
    widget/              bundle embutível (Fase 5)
  infra/
    terraform/           AWS: VPC, RDS, ElastiCache, ECS, S3, ALB, IAM, KMS
    docker/              Dockerfiles
  docker-compose.yml     dev local: postgres, redis, api, web, agent-worker, worker
  DECISIONS.md
  Makefile               make dev, make test, make migrate, make deploy
```

## Variáveis de ambiente (contrato)

Todas obrigatórias, exceto marcadas com `(opt)`.

```
# geral
APP_ENV=dev|staging|prod
APP_BASE_URL=https://app.voiceos.example
API_BASE_URL=https://api.voiceos.example
LOG_LEVEL=info

# banco / cache / storage
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
S3_BUCKET_RECORDINGS=voiceos-recordings
S3_BUCKET_DOCUMENTS=voiceos-documents
S3_BUCKET_EXPORTS=voiceos-exports
AWS_REGION=sa-east-1
KMS_KEY_ID=...

# auth
AUTH_SECRET=...
JWT_ISSUER=voiceos
JWT_AUDIENCE=voiceos-api
GOOGLE_CLIENT_ID=... (opt)
GOOGLE_CLIENT_SECRET=... (opt)
RESEND_API_KEY=...

# livekit
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
LIVEKIT_SIP_TRUNK_ID_INBOUND=...
LIVEKIT_SIP_TRUNK_ID_OUTBOUND=...

# provedores de voz / llm
DEEPGRAM_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...          # fallback STT/LLM + embeddings
ELEVENLABS_API_KEY=...
CARTESIA_API_KEY=... (opt)

# telefonia / mensagens
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_SIP_DOMAIN=...
WHATSAPP_APP_SECRET=... (opt)
WHATSAPP_VERIFY_TOKEN=... (opt)

# billing
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...

# observabilidade
OTEL_EXPORTER_OTLP_ENDPOINT=...
OTEL_EXPORTER_OTLP_HEADERS=...
SENTRY_DSN=...

# interno
INTERNAL_API_TOKEN=...      # agent-worker/worker → api
AGENT_WORKER_MAX_ROOMS=10
```

Segredos por tenant (chaves de tools do cliente, API keys de webhook) ficam na tabela `secrets`, criptografados com KMS envelope encryption. Nunca em env.

## Comunicação interna
- `agent-worker` e `worker` chamam a `api` em `/internal/*` com header `X-Internal-Token`. Só acessível na VPC (security group) e nunca exposto no ALB público.
- Eventos ao vivo (transcrição em andamento para o painel) vão por Redis pub/sub canal `tenant:{tenant_id}:call:{call_id}` e a `api` repassa via SSE em `GET /v1/calls/{id}/live`.

## Ambientes
| Ambiente | Onde | Dados |
|---|---|---|
| dev | Docker Compose local + LiveKit Cloud projeto `dev` | seed fake |
| staging | AWS conta única, prefixo `stg-` | cópia anonimizada |
| prod | AWS, prefixo `prd-` | real |

## Deploy
- CI: GitHub Actions. Em PR: lint, mypy, testes, build. Em `main`: build imagens → ECR → `terraform apply` (staging) → testes E2E → promoção manual para prod (workflow dispatch).
- Rolling update no ECS com health check `GET /health` (api) e `GET /health` (agent-worker expõe HTTP interno na porta 8081).
- `agent-worker` faz drain: ao receber SIGTERM, para de aceitar salas novas e espera as ativas terminarem (máx. 15 min).

## Trade-offs registrados
- **LiveKit Cloud vs self-host**: começar no Cloud elimina operar SFU/SIP. Migrar para self-host é trocar `LIVEKIT_URL` e subir os serviços; a spec já isola isso. Revisar quando custo de minutos do Cloud passar de 20% do custo total.
- **Um `agent-worker` para N salas**: simples e barato. Se um processo travar, N chamadas caem. Mitigação: `AGENT_WORKER_MAX_ROOMS=10` e health check agressivo. Revisar em > 500 chamadas simultâneas.
- **pgvector vs banco vetorial dedicado**: suficiente até ~5 M chunks. Revisar acima disso.
- **Cascata vs speech-to-speech**: cascata dá controle de custo, escolha de voz e tools maduras. Speech-to-speech entra como "provider" alternativo no pipeline em versão futura sem mudar o restante.
