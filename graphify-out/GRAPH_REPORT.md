# Graph Report - VOICE_OS  (2026-08-22)

## Corpus Check
- 159 files · ~72,735 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1267 nodes · 2866 edges · 100 communities (68 shown, 32 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 335 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4df7e988`
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
- evaluate
- LiveKitCallBridge
- WorkerAPI
- FakeEventBus
- repository.py
- CallAccounting
- postprocessing.py
- MemoryRuntimeCache
- RuntimeCache
- livekit_sessions.py
- DELETE
- GET
- PATCH
- POST
- PUT
- repository.py
- RedisRuntimeCache
- SessionGuards
- Repository protocol
- __init__.py
- request

## God Nodes (most connected - your core abstractions)
1. `Repository` - 72 edges
2. `PostgresRepository` - 70 edges
3. `MemoryRepository` - 70 edges
4. `get_settings()` - 42 edges
5. `Settings` - 38 edges
6. `VoiceSession` - 37 edges
7. `_require_admin()` - 36 edges
8. `ToolRegistry` - 30 edges
9. `LLMResponse` - 28 edges
10. `WorkerAPI` - 27 edges

## Surprising Connections (you probably didn't know these)
- `test_room_metadata_parses_dispatch_contract()` --calls--> `room_metadata()`  [INFERRED]
  tests/test_livekit_worker.py → apps/agent-worker/voiceos_voice/livekit_worker.py
- `test_room_metadata_rejects_invalid_dispatch_contract()` --calls--> `room_metadata()`  [INFERRED]
  tests/test_livekit_worker.py → apps/agent-worker/voiceos_voice/livekit_worker.py
- `test_start_egress_uses_audio_only_ogg_and_tenant_scoped_s3_key()` --calls--> `start_egress()`  [INFERRED]
  tests/test_recording.py → apps/agent-worker/voiceos_voice/recording.py
- `get_settings()` --calls--> `test_invalid_token_and_wrong_tenant()`  [INFERRED]
  apps/api/voiceos_api/config.py → tests/test_api.py
- `test_postgres_agent_and_call_lifecycle()` --calls--> `PostgresRepository`  [INFERRED]
  tests/test_postgres_repository.py → apps/api/voiceos_api/repository.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Provider-neutral Voice Turn Pipeline** — apps_agent_worker_voiceos_voice_session_voice_session, apps_agent_worker_voiceos_voice_contracts_provider_protocols, apps_agent_worker_voiceos_voice_resilience_provider_failover, apps_agent_worker_voiceos_voice_tools_tool_registry, apps_agent_worker_voiceos_voice_session_rag_guard [EXTRACTED 1.00]
- **Tenant Agent Version Management Flow** — apps_api_voiceos_api_routes_agent_version_lifecycle, apps_api_voiceos_api_repository_postgres_rls, apps_api_voiceos_api_schemas_api_contracts, scripts_test_agent_versions_acceptance [INFERRED 0.95]
- **Phase 0 Local Acceptance Stack** — compose_local_platform, phase_0_local_acceptance, scripts_test_auth_flow_acceptance, scripts_test_rls_acceptance, scripts_smoke_local_stack [EXTRACTED 1.00]

## Communities (100 total, 32 thin omitted)

### Community 0 - "Voice Core Modules"
Cohesion: 0.06
Nodes (66): BaseModel, simulate(), SimulationRequest, SimulationResponse, WorkerState, LLMProvider, LLMResponse, Any (+58 more)

### Community 1 - "API Authentication Routes"
Cohesion: 0.15
Nodes (10): ElevenLabsVoicePreview, get_voice_preview(), Any, AsyncBaseTransport, Protocol, Response, UnavailableVoicePreview, VoicePreview (+2 more)

### Community 3 - "VoiceOS Platform Architecture"
Cohesion: 0.06
Nodes (34): AWS sa-east-1 Data Plane, LiveKit-based Voice Stack, Python 3.12 Backend, VoiceOS Multi-tenant Voice Agent Platform, Six-phase Delivery Roadmap, Controller and Processor Roles, LGPD Incident Runbook, VoiceOS Subprocessor Registry (+26 more)

### Community 4 - "Database Repository Layer"
Cohesion: 0.04
Nodes (47): dependencies, @auth/core, @auth/pg-adapter, livekit-client, next, next-auth, pg, react (+39 more)

### Community 5 - "API Schemas and Mock"
Cohesion: 0.06
Nodes (131): alias, get_agent_template(), list_agent_templates(), Any, chunk_text(), extract_url(), agent_templates(), append_call_events() (+123 more)

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
Cohesion: 0.08
Nodes (21): GET(), proxy(), createWorkspace(), databaseUrl, OnboardingWizard(), emailProvider, providers, secureCookies (+13 more)

### Community 26 - "Authentication Flow Test"
Cohesion: 0.50
Nodes (3): OpenerDirector, opener(), Exercise the development magic-link login against the running stack.

### Community 27 - "Voice Worker Tests"
Cohesion: 0.15
Nodes (12): openapi-typescript, devDependencies, openapi-typescript, typescript, typescript, name, private, scripts (+4 more)

### Community 29 - "Web Middleware"
Cohesion: 0.17
Nodes (11): devDependencies, typescript, files, typescript, name, scripts, build, typecheck (+3 more)

### Community 32 - "Dashboard Page"
Cohesion: 0.11
Nodes (13): AgentTab, agentTabs, AgentTemplate, api(), Call, Dashboard(), Document, Item (+5 more)

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
Cohesion: 0.17
Nodes (13): get_settings(), Settings, get_livekit_sessions(), LiveKitSessions, Any, UUID, get_recording_storage(), Any (+5 more)

### Community 41 - "ESLint Configuration"
Cohesion: 0.33
Nodes (5): Como usar este pacote, Decisões fechadas (não reabrir), Especificação Técnica — Plataforma de Agentes de Voz Multi-tenant, Regras para o agente executor, Índice

### Community 42 - "Next Type Declarations"
Cohesion: 0.50
Nodes (3): compat, config, directory

### Community 63 - "Any"
Cohesion: 0.07
Nodes (3): Any, Protocol, Repository

### Community 64 - "PostgresRepository"
Cohesion: 0.10
Nodes (3): immutable agent publish flow, PostgresRepository, tenant_session()

### Community 65 - "knowledge.py"
Cohesion: 0.18
Nodes (8): Embeddings, extract_bytes(), get_embeddings(), AsyncBaseTransport, _TextExtractor, HTMLParser, test_chunk_text_respects_overlap_and_boundaries(), test_extract_html_upload()

### Community 66 - "get_settings"
Cohesion: 0.09
Nodes (23): FakeEventBus, FakePromptImprover, FakeRecordingStorage, FakeVoicePreview, headers(), HealthyChecker, test_agent_draft_versions_and_rollback(), test_agent_publish_session_and_isolation() (+15 more)

### Community 67 - "test_health.py"
Cohesion: 0.14
Nodes (11): get_health_checker(), HealthChecker, Any, MonkeyPatch, FakeConnection, FakeConnectionContext, FakeEngine, FakeRedis (+3 more)

### Community 68 - "tool_execution.py"
Cohesion: 0.29
Nodes (11): get_tool_executor(), _json_path(), _lookup(), Any, _render(), _safe_url(), ToolExecutor, test_webhook_bearer_secret_is_applied() (+3 more)

### Community 69 - "HealthChecker"
Cohesion: 0.15
Nodes (11): get_native_integrations(), NativeIntegrations, Any, AsyncBaseTransport, UUID, EnvelopeCipher, get_secret_cipher(), Protocol (+3 more)

### Community 71 - "MemoryStore"
Cohesion: 0.15
Nodes (16): AgentSession, dynamic_tools(), _jsonable(), LiveKitCallBridge, provider_pipeline(), Any, MetricsCollectedEvent, SessionUsageUpdatedEvent (+8 more)

### Community 72 - "evaluate"
Cohesion: 0.36
Nodes (8): evaluate(), fetch_calls(), main(), percentile(), Any, Verify Phase 1 media acceptance from real staging call records., test_phase1_staging_acceptance_fails_without_external_evidence(), test_phase1_staging_acceptance_requires_and_validates_real_metrics()

### Community 73 - "LiveKitCallBridge"
Cohesion: 0.16
Nodes (16): VoiceOS FastAPI application, AsyncSession, session(), health(), http_error(), Any, Request, Response (+8 more)

### Community 74 - "WorkerAPI"
Cohesion: 0.41
Nodes (3): Any, UUID, WorkerAPI

### Community 76 - "FakeEventBus"
Cohesion: 0.60
Nodes (4): internal_token(), Principal, UUID, Header

### Community 77 - "repository.py"
Cohesion: 0.39
Nodes (7): EgressStarter, Protocol, UUID, start_egress(), start_room_recording(), EgressInfo, RoomCompositeEgressRequest

### Community 78 - "CallAccounting"
Cohesion: 0.20
Nodes (8): CallAccounting, _percentile(), Any, MetricsCollectedEvent, SessionUsageUpdatedEvent, _rate(), test_accounting_aggregates_latency_usage_and_cost(), test_representative_web_minute_cost_model_is_within_rnf_09()

### Community 79 - "postprocessing.py"
Cohesion: 0.29
Nodes (3): AsyncBaseTransport, Protocol, RuntimeCache

### Community 80 - "MemoryRuntimeCache"
Cohesion: 0.21
Nodes (8): MemoryRuntimeCache, test_call_bridge_persists_final_transcript_and_closes_call(), test_dynamic_tools_mutate_variables_and_proxy_remote_execution(), test_room_metadata_parses_dispatch_contract(), test_room_metadata_rejects_invalid_dispatch_contract(), test_api_retries_three_times_then_fails(), test_runtime_is_cached_and_internal_calls_are_persisted(), UserInputTranscribedEvent

### Community 81 - "RuntimeCache"
Cohesion: 0.16
Nodes (9): cosine_similarity(), get_repository(), MemoryStore, Any, UUID, Deterministic dev adapter. Production endpoints use the same contract with Postg, test_egress_webhook_maps_completed_file_to_recording(), test_memory_repository_upserts_recording_into_call_detail() (+1 more)

### Community 82 - "livekit_sessions.py"
Cohesion: 0.43
Nodes (6): email(), EmailMessage, get_last_email(), health(), BaseModel, tool()

### Community 89 - "repository.py"
Cohesion: 0.08
Nodes (15): AnthropicPostprocessor, get_postprocessor(), Postprocessor, Any, AsyncBaseTransport, Protocol, LastOwnerError, Raised when a membership mutation would leave a tenant without an owner. (+7 more)

### Community 91 - "SessionGuards"
Cohesion: 0.38
Nodes (3): SessionGuards, test_session_guards_prompt_once_then_end_after_second_silence(), UserStateChangedEvent

### Community 92 - "Repository protocol"
Cohesion: 0.15
Nodes (9): AnthropicPromptImprover, get_prompt_improver(), PromptImprover, AsyncBaseTransport, Protocol, UnavailablePromptImprover, RuntimeError, test_prompt_improver_preserves_jinja_variables() (+1 more)

### Community 99 - "request"
Cohesion: 0.50
Nodes (4): internal_request(), Any, Exercise agent draft, publish, version history and rollback against PostgreSQL., request()

## Knowledge Gaps
- **188 isolated node(s):** `Item`, `Call`, `Document`, `AgentTemplate`, `Section` (+183 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Repository` connect `Any` to `Voice Core Modules`, `Memory Repository Operations`, `API Schemas and Mock`, `HealthChecker`, `RuntimeCache`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `MemoryRepository` connect `Memory Repository Operations` to `PostgresRepository`, `.get_agent`, `.get_call`, `get_settings`, `HealthChecker`, `Backend Design Rationale`, `RuntimeCache`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `PostgresRepository` connect `PostgresRepository` to `.get_agent`, `Memory Repository Operations`, `.get_call`, `._internal_session`, `Backend Design Rationale`, `RuntimeCache`, `repository.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Repository` (e.g. with `NativeIntegrations` and `MemoryStore`) actually correct?**
  _`Repository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `PostgresRepository` (e.g. with `MemoryRepository` and `MemoryStore`) actually correct?**
  _`PostgresRepository` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `MemoryRepository` (e.g. with `MemoryStore` and `HealthyChecker`) actually correct?**
  _`MemoryRepository` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Item`, `Call`, `Document` to the rest of the system?**
  _188 weakly-connected nodes found - possible documentation gaps or missing edges._