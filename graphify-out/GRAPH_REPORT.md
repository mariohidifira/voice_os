# Graph Report - VOICE_OS  (2026-08-20)

## Corpus Check
- 118 files · ~43,650 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 965 nodes · 2115 edges · 79 communities (50 shown, 29 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 228 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `443af6a3`
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
- test_agent_versions.py
- FakeEventBus
- repository.py
- Repository protocol

## God Nodes (most connected - your core abstractions)
1. `Repository` - 61 edges
2. `PostgresRepository` - 58 edges
3. `MemoryRepository` - 56 edges
4. `VoiceSession` - 35 edges
5. `Settings` - 30 edges
6. `get_settings()` - 30 edges
7. `ToolRegistry` - 28 edges
8. `LLMResponse` - 26 edges
9. `MockLLM` - 19 edges
10. `WorkerAPI` - 18 edges

## Surprising Connections (you probably didn't know these)
- `test_postgres_agent_and_call_lifecycle()` --calls--> `PostgresRepository`  [INFERRED]
  tests/test_postgres_repository.py → apps/api/voiceos_api/repository.py
- `Phase 1 voice runtime` --defines_typed_contracts_for--> `RuntimeConfig`  [EXTRACTED]
  PHASE-1-REPORT.md → packages/shared-py/voiceos_shared/contracts.py
- `Tenant-scoped row-level security` --validates_tenant_isolation_behavior--> `Agent publish, session and isolation test`  [INFERRED]
  PHASE-0-REPORT.md → tests/test_api.py
- `Phase 4 WhatsApp processing` --uses_async_worker_boundary--> `run worker loop`  [INFERRED]
  PHASE-4-REPORT.md → apps/worker/main.py
- `Voice Provider Protocols` --conceptually_related_to--> `LiveKit Deepgram Anthropic OpenAI ElevenLabs Voice Stack`  [INFERRED]
  apps/agent-worker/voiceos_voice/contracts.py → PROVIDER-SETUP-CHECKLIST.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Provider-neutral Voice Turn Pipeline** — apps_agent_worker_voiceos_voice_session_voice_session, apps_agent_worker_voiceos_voice_contracts_provider_protocols, apps_agent_worker_voiceos_voice_resilience_provider_failover, apps_agent_worker_voiceos_voice_tools_tool_registry, apps_agent_worker_voiceos_voice_session_rag_guard [EXTRACTED 1.00]
- **Tenant Agent Version Management Flow** — apps_api_voiceos_api_routes_agent_version_lifecycle, apps_api_voiceos_api_repository_postgres_rls, apps_api_voiceos_api_schemas_api_contracts, scripts_test_agent_versions_acceptance [INFERRED 0.95]
- **Phase 0 Local Acceptance Stack** — compose_local_platform, phase_0_local_acceptance, scripts_test_auth_flow_acceptance, scripts_test_rls_acceptance, scripts_smoke_local_stack [EXTRACTED 1.00]

## Communities (79 total, 29 thin omitted)

### Community 0 - "Voice Core Modules"
Cohesion: 0.06
Nodes (62): BaseModel, simulate(), SimulationRequest, SimulationResponse, WorkerState, LLMProvider, LLMResponse, Any (+54 more)

### Community 1 - "API Authentication Routes"
Cohesion: 0.15
Nodes (16): VoiceOS FastAPI application, AsyncSession, session(), health(), http_error(), Any, Request, ready() (+8 more)

### Community 3 - "VoiceOS Platform Architecture"
Cohesion: 0.06
Nodes (34): AWS sa-east-1 Data Plane, LiveKit-based Voice Stack, Python 3.12 Backend, VoiceOS Multi-tenant Voice Agent Platform, Six-phase Delivery Roadmap, Controller and Processor Roles, LGPD Incident Runbook, VoiceOS Subprocessor Registry (+26 more)

### Community 4 - "Database Repository Layer"
Cohesion: 0.05
Nodes (39): dependencies, @auth/core, @auth/pg-adapter, next, next-auth, pg, react, react-dom (+31 more)

### Community 5 - "API Schemas and Mock"
Cohesion: 0.08
Nodes (94): alias, extract_url(), append_call_events(), append_call_tool_call(), append_call_turns(), calls(), create_agent(), create_document() (+86 more)

### Community 6 - "Health Checks"
Cohesion: 0.08
Nodes (25): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+17 more)

### Community 7 - "Backend Design Rationale"
Cohesion: 0.14
Nodes (15): Auth.js PostgreSQL schema, asynchronous database session factory, idempotent development seed, internal API token authentication, VoiceOS NextAuth configuration, tenant-scoped Principal, principal bearer-token authentication, provider and tool mock service (+7 more)

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
Cohesion: 0.11
Nodes (3): immutable agent publish flow, PostgresRepository, tenant_session()

### Community 65 - "knowledge.py"
Cohesion: 0.17
Nodes (9): chunk_text(), Embeddings, extract_bytes(), get_embeddings(), AsyncBaseTransport, _TextExtractor, HTMLParser, test_chunk_text_respects_overlap_and_boundaries() (+1 more)

### Community 66 - "get_settings"
Cohesion: 0.16
Nodes (17): internal_token(), Principal, UUID, get_settings(), Header, headers(), HealthyChecker, test_agent_draft_versions_and_rollback() (+9 more)

### Community 67 - "test_health.py"
Cohesion: 0.15
Nodes (13): Settings, get_health_checker(), HealthChecker, Any, BaseSettings, MonkeyPatch, FakeConnection, FakeConnectionContext (+5 more)

### Community 68 - "tool_execution.py"
Cohesion: 0.25
Nodes (11): get_tool_executor(), _json_path(), _lookup(), Any, AsyncBaseTransport, _render(), _safe_url(), ToolExecutor (+3 more)

### Community 69 - "HealthChecker"
Cohesion: 0.14
Nodes (11): get_native_integrations(), NativeIntegrations, Any, AsyncBaseTransport, UUID, EnvelopeCipher, get_secret_cipher(), Protocol (+3 more)

### Community 71 - "MemoryStore"
Cohesion: 0.29
Nodes (4): MemoryStore, Any, UUID, Deterministic dev adapter. Production endpoints use the same contract with Postg

### Community 72 - ".get_call"
Cohesion: 0.13
Nodes (10): MemoryRuntimeCache, Any, AsyncBaseTransport, Protocol, UUID, RedisRuntimeCache, RuntimeCache, WorkerAPI (+2 more)

### Community 74 - "test_agent_versions.py"
Cohesion: 0.50
Nodes (4): internal_request(), Any, Exercise agent draft, publish, version history and rollback against PostgreSQL., request()

## Knowledge Gaps
- **167 isolated node(s):** `databaseUrl`, `stats`, `emailProvider`, `providers`, `secureCookies` (+162 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Repository` connect `Any` to `Voice Core Modules`, `Memory Repository Operations`, `HealthChecker`, `API Schemas and Mock`, `MemoryStore`, `repository.py`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `PostgresRepository` connect `PostgresRepository` to `Voice Core Modules`, `Memory Repository Operations`, `._internal_session`, `MemoryStore`, `Backend Design Rationale`, `auth.py`, `repository.py`, `Repository protocol`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `MemoryRepository` connect `Memory Repository Operations` to `PostgresRepository`, `get_settings`, `HealthChecker`, `MemoryStore`, `auth.py`, `FakeEventBus`, `repository.py`, `Repository protocol`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Repository` (e.g. with `NativeIntegrations` and `MemoryStore`) actually correct?**
  _`Repository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `PostgresRepository` (e.g. with `MemoryRepository` and `MemoryStore`) actually correct?**
  _`PostgresRepository` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `MemoryRepository` (e.g. with `MemoryStore` and `HealthyChecker`) actually correct?**
  _`MemoryRepository` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `databaseUrl`, `stats`, `emailProvider` to the rest of the system?**
  _167 weakly-connected nodes found - possible documentation gaps or missing edges._