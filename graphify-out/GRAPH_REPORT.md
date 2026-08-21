# Graph Report - VOICE_OS  (2026-08-21)

## Corpus Check
- 127 files · ~46,635 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1053 nodes · 2322 edges · 83 communities (56 shown, 27 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 259 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b792887e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Voice Core Modules
- API Authentication Routes
- Memory Repository Operations
- VoiceOS Platform Architecture
- Database Repository Layer
- API Schemas and Mock
- Health Checks
- Backend Design Rationale
- Phase Zero Architecture
- Voice Runtime Concepts
- Provider Resilience
- Generated Runtime Contracts
- Embeddable Voice Widget
- Alembic Runtime
- Migration Tests
- Tenant Isolation Foundation
- Web Dashboard Pages
- Worker Lifecycle
- Initial Database Migration
- Auth Database Migration
- Forced RLS Migration
- RLS Acceptance Test
- Development Seed
- Background Worker Phases
- JWT Token Route
- Authentication Flow Test
- Voice Worker Tests
- API Package
- Web Middleware
- Web Home Page
- Dashboard Page
- Job Worker
- Worker Shutdown Model
- FastAPI Observability
- Widget Architecture
- API Error Contracts
- Authorization Configuration
- Auth Runtime
- ESLint Configuration
- Next Type Declarations
- OpenAPI Types
- OpenAPI Generation
- Smoke Test
- Async Migration Dispatch
- Tool Validation Contract
- Portuguese Web Layout
- Telephony Phase
- Billing Governance Phase
- Auth HTTP Handlers
- Runtime Settings
- Demo Tenant Seed
- Local Stack Verification
- { GET, POST }
- voiceos
- Any
- PostgresRepository
- knowledge.py
- get_settings
- test_health.py
- tool_execution.py
- HealthChecker
- ._internal_session
- MemoryStore
- .get_call
- livekit_worker.py
- test_agent_versions.py
- FakeEventBus
- repository.py
- CallAccounting
- postprocessing.py
- MemoryRuntimeCache
- Settings
- SessionGuards

## God Nodes (most connected - your core abstractions)
1. `Repository` - 63 edges
2. `PostgresRepository` - 59 edges
3. `MemoryRepository` - 58 edges
4. `VoiceSession` - 35 edges
5. `get_settings()` - 34 edges
6. `Settings` - 30 edges
7. `ToolRegistry` - 28 edges
8. `WorkerAPI` - 27 edges
9. `LLMResponse` - 26 edges
10. `voiceos_agent()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `test_start_egress_uses_audio_only_ogg_and_tenant_scoped_s3_key()` --calls--> `start_egress()`  [INFERRED]
  tests/test_recording.py → apps/agent-worker/voiceos_voice/recording.py
- `get_settings()` --calls--> `test_invalid_token_and_wrong_tenant()`  [INFERRED]
  apps/api/voiceos_api/config.py → tests/test_api.py
- `test_postgres_agent_and_call_lifecycle()` --calls--> `PostgresRepository`  [INFERRED]
  tests/test_postgres_repository.py → apps/api/voiceos_api/repository.py
- `test_egress_webhook_maps_completed_file_to_recording()` --calls--> `_egress_recording()`  [INFERRED]
  tests/test_recording.py → apps/api/voiceos_api/routes.py
- `Phase 1 voice runtime` --defines_typed_contracts_for--> `RuntimeConfig`  [EXTRACTED]
  PHASE-1-REPORT.md → packages/shared-py/voiceos_shared/contracts.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Provider-neutral Voice Turn Pipeline** — apps_agent_worker_voiceos_voice_session_voice_session, apps_agent_worker_voiceos_voice_contracts_provider_protocols, apps_agent_worker_voiceos_voice_resilience_provider_failover, apps_agent_worker_voiceos_voice_tools_tool_registry, apps_agent_worker_voiceos_voice_session_rag_guard [EXTRACTED 1.00]
- **Tenant Agent Version Management Flow** — apps_api_voiceos_api_routes_agent_version_lifecycle, apps_api_voiceos_api_repository_postgres_rls, apps_api_voiceos_api_schemas_api_contracts, scripts_test_agent_versions_acceptance [INFERRED 0.95]
- **Phase 0 Local Acceptance Stack** — compose_local_platform, phase_0_local_acceptance, scripts_test_auth_flow_acceptance, scripts_test_rls_acceptance, scripts_smoke_local_stack [EXTRACTED 1.00]

## Communities (83 total, 27 thin omitted)

### Community 0 - "Voice Core Modules"
Cohesion: 0.06
Nodes (62): BaseModel, simulate(), SimulationRequest, SimulationResponse, WorkerState, LLMProvider, LLMResponse, Any (+54 more)

### Community 1 - "API Authentication Routes"
Cohesion: 0.15
Nodes (17): VoiceOS FastAPI application, AsyncSession, session(), get_health_checker(), health(), http_error(), Any, Request (+9 more)

### Community 3 - "VoiceOS Platform Architecture"
Cohesion: 0.06
Nodes (34): AWS sa-east-1 Data Plane, LiveKit-based Voice Stack, Python 3.12 Backend, VoiceOS Multi-tenant Voice Agent Platform, Six-phase Delivery Roadmap, Controller and Processor Roles, LGPD Incident Runbook, VoiceOS Subprocessor Registry (+26 more)

### Community 4 - "Database Repository Layer"
Cohesion: 0.05
Nodes (39): dependencies, @auth/core, @auth/pg-adapter, next, next-auth, pg, react, react-dom (+31 more)

### Community 5 - "API Schemas and Mock"
Cohesion: 0.07
Nodes (99): alias, extract_url(), append_call_events(), append_call_tool_call(), append_call_turns(), calls(), create_agent(), create_document() (+91 more)

### Community 6 - "Health Checks"
Cohesion: 0.08
Nodes (25): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+17 more)

### Community 7 - "Backend Design Rationale"
Cohesion: 0.12
Nodes (17): Repository protocol, Auth.js PostgreSQL schema, asynchronous database session factory, idempotent development seed, internal API token authentication, VoiceOS NextAuth configuration, tenant-scoped Principal, principal bearer-token authentication (+9 more)

### Community 8 - "Phase Zero Architecture"
Cohesion: 0.05
Nodes (41): Agent Worker HTTP Server, Voice Worker Simulation API, Agent Worker Drain State, LLM Response and Tool Call Contracts, Voice Provider Protocols, Sandboxed Contextual System Prompt, Mock Voice Provider Stack, Provider Retry Fallback and Circuit Breaker (+33 more)

### Community 9 - "Voice Runtime Concepts"
Cohesion: 0.22
Nodes (10): channel_name(), encode_sse(), EventBus, get_event_bus(), Any, Protocol, UUID, RedisEventBus (+2 more)

### Community 10 - "Provider Resilience"
Cohesion: 0.13
Nodes (14): name, postcss, sharp, overrides, next, private, scripts, build (+6 more)

### Community 11 - "Generated Runtime Contracts"
Cohesion: 0.18
Nodes (12): API authorization tests, ErrorBody, ErrorEnvelope, BaseModel, RuntimeConfig, Shared contracts for VoiceOS services., Generated OpenAPI TypeScript contract, Phase 1 voice runtime (+4 more)

### Community 13 - "Alembic Runtime"
Cohesion: 0.60
Nodes (3): run_async_migrations(), run_migrations_online(), run_sync_migrations()

### Community 14 - "Migration Tests"
Cohesion: 0.70
Nodes (4): load_initial_migration(), test_every_tenant_table_has_rls_contract(), test_join_tables_have_one_primary_key_and_unique_scope(), test_required_phase_zero_tables_exist()

### Community 15 - "Tenant Isolation Foundation"
Cohesion: 0.40
Nodes (5): Agent publish, session and isolation test, Migration and RLS contract tests, Phase 0 platform foundation, SQL-first exhaustive migration, Tenant-scoped row-level security

### Community 16 - "Web Dashboard Pages"
Cohesion: 0.50
Nodes (5): Tenant dashboard, emailLogin, googleLogin, Home, Login

### Community 17 - "Worker Lifecycle"
Cohesion: 0.33
Nodes (3): main(), WorkerState, agent worker graceful shutdown

### Community 21 - "RLS Acceptance Test"
Cohesion: 0.60
Nodes (4): main(), UUID, Real PostgreSQL RLS acceptance check for tenants, agents and calls., visible_count()

### Community 24 - "Background Worker Phases"
Cohesion: 0.67
Nodes (3): run worker loop, Local Docker Compose stack, Phase 4 WhatsApp processing

### Community 25 - "JWT Token Route"
Cohesion: 0.11
Nodes (10): base64url(), databaseUrl, GET(), emailProvider, providers, secureCookies, databaseUrl, { handlers, auth, signIn, signOut } (+2 more)

### Community 26 - "Authentication Flow Test"
Cohesion: 0.50
Nodes (3): OpenerDirector, opener(), Exercise the development magic-link login against the running stack.

### Community 27 - "Voice Worker Tests"
Cohesion: 0.15
Nodes (12): openapi-typescript, devDependencies, openapi-typescript, typescript, typescript, name, private, scripts (+4 more)

### Community 29 - "Web Middleware"
Cohesion: 0.17
Nodes (11): devDependencies, typescript, files, typescript, name, scripts, build, typecheck (+3 more)

### Community 34 - "Worker Shutdown Model"
Cohesion: 0.27
Nodes (8): ApiError, Role, Session, components, $defs, operations, paths, webhooks

### Community 35 - "FastAPI Observability"
Cohesion: 0.20
Nodes (9): compilerOptions, declaration, module, moduleResolution, outDir, strict, target, include (+1 more)

### Community 37 - "API Error Contracts"
Cohesion: 0.20
Nodes (9): compilerOptions, declaration, module, moduleResolution, outDir, strict, target, include (+1 more)

### Community 38 - "Authorization Configuration"
Cohesion: 0.22
Nodes (8): 14 — Fases de Execução, Depois da Fase 5 (backlog priorizado, não especificado aqui), Fase 0 — Fundação (1 semana), Fase 1 — Agente de voz por WebRTC + painel essencial (3–4 semanas), Fase 2 — Telefone (3 semanas), Fase 3 — Billing, API pública, qualidade, LGPD (2–3 semanas), Fase 4 — WhatsApp e simulador (2–3 semanas), Fase 5 — Widget embutível, SDK, white-label (2 semanas)

### Community 40 - "Auth Runtime"
Cohesion: 0.43
Nodes (6): email(), EmailMessage, get_last_email(), health(), BaseModel, tool()

### Community 41 - "ESLint Configuration"
Cohesion: 0.33
Nodes (5): Como usar este pacote, Decisões fechadas (não reabrir), Especificação Técnica — Plataforma de Agentes de Voz Multi-tenant, Regras para o agente executor, Índice

### Community 42 - "Next Type Declarations"
Cohesion: 0.50
Nodes (3): compat, config, directory

### Community 63 - "Any"
Cohesion: 0.08
Nodes (3): Protocol, UUID, Repository

### Community 64 - "PostgresRepository"
Cohesion: 0.12
Nodes (3): immutable agent publish flow, PostgresRepository, tenant_session()

### Community 65 - "knowledge.py"
Cohesion: 0.17
Nodes (9): chunk_text(), Embeddings, extract_bytes(), get_embeddings(), AsyncBaseTransport, _TextExtractor, HTMLParser, test_chunk_text_respects_overlap_and_boundaries() (+1 more)

### Community 66 - "get_settings"
Cohesion: 0.08
Nodes (20): MemoryStore, Any, UUID, Deterministic dev adapter. Production endpoints use the same contract with Postg, FakeEventBus, headers(), HealthyChecker, test_agent_draft_versions_and_rollback() (+12 more)

### Community 67 - "test_health.py"
Cohesion: 0.15
Nodes (10): HealthChecker, Any, MonkeyPatch, FakeConnection, FakeConnectionContext, FakeEngine, FakeRedis, Any (+2 more)

### Community 68 - "tool_execution.py"
Cohesion: 0.31
Nodes (10): get_tool_executor(), _json_path(), _lookup(), Any, _render(), _safe_url(), ToolExecutor, test_webhook_bearer_secret_is_applied() (+2 more)

### Community 69 - "HealthChecker"
Cohesion: 0.24
Nodes (7): get_native_integrations(), NativeIntegrations, Any, AsyncBaseTransport, UUID, Protocol, SecretCipher

### Community 72 - ".get_call"
Cohesion: 0.22
Nodes (6): Any, AsyncBaseTransport, Protocol, UUID, RuntimeCache, WorkerAPI

### Community 73 - "livekit_worker.py"
Cohesion: 0.19
Nodes (13): AgentSession, dynamic_tools(), provider_pipeline(), Any, UUID, room_metadata(), voiceos_agent(), JobContext (+5 more)

### Community 74 - "test_agent_versions.py"
Cohesion: 0.23
Nodes (10): internal_token(), Principal, UUID, get_settings(), AsyncBaseTransport, Header, internal_request(), Any (+2 more)

### Community 76 - "FakeEventBus"
Cohesion: 0.20
Nodes (8): _jsonable(), LiveKitCallBridge, MetricsCollectedEvent, SessionUsageUpdatedEvent, CloseEvent, ConversationItemAddedEvent, test_call_bridge_persists_final_transcript_and_closes_call(), UserInputTranscribedEvent

### Community 77 - "repository.py"
Cohesion: 0.39
Nodes (7): EgressStarter, Protocol, UUID, start_egress(), start_room_recording(), EgressInfo, RoomCompositeEgressRequest

### Community 78 - "CallAccounting"
Cohesion: 0.21
Nodes (7): CallAccounting, _percentile(), Any, MetricsCollectedEvent, SessionUsageUpdatedEvent, _rate(), test_accounting_aggregates_latency_usage_and_cost()

### Community 79 - "postprocessing.py"
Cohesion: 0.22
Nodes (8): AnthropicPostprocessor, get_postprocessor(), Postprocessor, Any, AsyncBaseTransport, Protocol, test_postprocessor_retries_invalid_provider_response(), test_postprocessor_sends_transcript_and_validates_structured_result()

### Community 80 - "MemoryRuntimeCache"
Cohesion: 0.21
Nodes (4): MemoryRuntimeCache, RedisRuntimeCache, test_api_retries_three_times_then_fails(), test_runtime_is_cached_and_internal_calls_are_persisted()

### Community 81 - "Settings"
Cohesion: 0.27
Nodes (6): Settings, EnvelopeCipher, get_secret_cipher(), BaseSettings, test_google_oauth_refresh_calendar_and_resend(), test_local_envelope_cipher_roundtrip()

### Community 82 - "SessionGuards"
Cohesion: 0.38
Nodes (3): SessionGuards, test_session_guards_prompt_once_then_end_after_second_silence(), UserStateChangedEvent

## Knowledge Gaps
- **167 isolated node(s):** `databaseUrl`, `stats`, `emailProvider`, `providers`, `secureCookies` (+162 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Repository` connect `Any` to `Voice Core Modules`, `Memory Repository Operations`, `get_settings`, `HealthChecker`, `API Schemas and Mock`, `MemoryStore`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `PostgresRepository` connect `PostgresRepository` to `Voice Core Modules`, `Memory Repository Operations`, `get_settings`, `._internal_session`, `Backend Design Rationale`, `MemoryStore`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `MemoryRepository` connect `Memory Repository Operations` to `PostgresRepository`, `get_settings`, `._internal_session`, `Backend Design Rationale`, `MemoryStore`, `Settings`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Repository` (e.g. with `NativeIntegrations` and `MemoryStore`) actually correct?**
  _`Repository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `PostgresRepository` (e.g. with `MemoryRepository` and `MemoryStore`) actually correct?**
  _`PostgresRepository` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `MemoryRepository` (e.g. with `MemoryStore` and `HealthyChecker`) actually correct?**
  _`MemoryRepository` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `databaseUrl`, `stats`, `emailProvider` to the rest of the system?**
  _167 weakly-connected nodes found - possible documentation gaps or missing edges._