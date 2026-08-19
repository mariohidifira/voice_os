# Graph Report - G:\DEV\VOICE_OS  (2026-08-19)

## Corpus Check
- Corpus is ~28,212 words - fits in a single context window. You may not need a graph.

## Summary
- 432 nodes · 602 edges · 40 communities detected
- Extraction: 78% EXTRACTED · 22% INFERRED · 0% AMBIGUOUS · INFERRED: 130 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Voice Core Modules|Voice Core Modules]]
- [[_COMMUNITY_API Authentication Routes|API Authentication Routes]]
- [[_COMMUNITY_Memory Repository Operations|Memory Repository Operations]]
- [[_COMMUNITY_VoiceOS Platform Architecture|VoiceOS Platform Architecture]]
- [[_COMMUNITY_Database Repository Layer|Database Repository Layer]]
- [[_COMMUNITY_API Schemas and Mock|API Schemas and Mock]]
- [[_COMMUNITY_Health Checks|Health Checks]]
- [[_COMMUNITY_Backend Design Rationale|Backend Design Rationale]]
- [[_COMMUNITY_Phase Zero Architecture|Phase Zero Architecture]]
- [[_COMMUNITY_Voice Runtime Concepts|Voice Runtime Concepts]]
- [[_COMMUNITY_Provider Resilience|Provider Resilience]]
- [[_COMMUNITY_Generated Runtime Contracts|Generated Runtime Contracts]]
- [[_COMMUNITY_Embeddable Voice Widget|Embeddable Voice Widget]]
- [[_COMMUNITY_Alembic Runtime|Alembic Runtime]]
- [[_COMMUNITY_Migration Tests|Migration Tests]]
- [[_COMMUNITY_Tenant Isolation Foundation|Tenant Isolation Foundation]]
- [[_COMMUNITY_Web Dashboard Pages|Web Dashboard Pages]]
- [[_COMMUNITY_Worker Lifecycle|Worker Lifecycle]]
- [[_COMMUNITY_Initial Database Migration|Initial Database Migration]]
- [[_COMMUNITY_Auth Database Migration|Auth Database Migration]]
- [[_COMMUNITY_Forced RLS Migration|Forced RLS Migration]]
- [[_COMMUNITY_RLS Acceptance Test|RLS Acceptance Test]]
- [[_COMMUNITY_Development Seed|Development Seed]]
- [[_COMMUNITY_Background Worker Phases|Background Worker Phases]]
- [[_COMMUNITY_JWT Token Route|JWT Token Route]]
- [[_COMMUNITY_Authentication Flow Test|Authentication Flow Test]]
- [[_COMMUNITY_API Package|API Package]]
- [[_COMMUNITY_Worker Shutdown Model|Worker Shutdown Model]]
- [[_COMMUNITY_FastAPI Observability|FastAPI Observability]]
- [[_COMMUNITY_Widget Architecture|Widget Architecture]]
- [[_COMMUNITY_API Error Contracts|API Error Contracts]]
- [[_COMMUNITY_Async Migration Dispatch|Async Migration Dispatch]]
- [[_COMMUNITY_Tool Validation Contract|Tool Validation Contract]]
- [[_COMMUNITY_Portuguese Web Layout|Portuguese Web Layout]]
- [[_COMMUNITY_Telephony Phase|Telephony Phase]]
- [[_COMMUNITY_Billing Governance Phase|Billing Governance Phase]]
- [[_COMMUNITY_Auth HTTP Handlers|Auth HTTP Handlers]]
- [[_COMMUNITY_Runtime Settings|Runtime Settings]]
- [[_COMMUNITY_Demo Tenant Seed|Demo Tenant Seed]]
- [[_COMMUNITY_Local Stack Verification|Local Stack Verification]]

## God Nodes (most connected - your core abstractions)
1. `VoiceSession` - 25 edges
2. `ToolRegistry` - 20 edges
3. `MemoryRepository` - 19 edges
4. `Repository` - 18 edges
5. `PostgresRepository` - 17 edges
6. `LLMResponse` - 17 edges
7. `tenant_session()` - 14 edges
8. `MockLLM` - 14 edges
9. `MockTTS` - 14 edges
10. `HealthChecker` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Tenant-scoped row-level security` --validates_tenant_isolation_behavior--> `Agent publish, session and isolation test`  [INFERRED]
  PHASE-0-REPORT.md → tests/test_api.py
- `Phase 4 WhatsApp processing` --uses_async_worker_boundary--> `run worker loop`  [INFERRED]
  PHASE-4-REPORT.md → apps/worker/main.py
- `Voice Worker Simulation API` --implements--> `Seven-service Local VoiceOS Platform`  [EXTRACTED]
  apps/agent-worker/voiceos_voice/app.py → docker-compose.yml
- `Voice Provider Protocols` --conceptually_related_to--> `LiveKit Deepgram Anthropic OpenAI ElevenLabs Voice Stack`  [INFERRED]
  apps/agent-worker/voiceos_voice/contracts.py → PROVIDER-SETUP-CHECKLIST.md
- `get_settings()` --calls--> `test_invalid_token_and_wrong_tenant()`  [INFERRED]
  apps/api/voiceos_api/config.py → tests/test_api.py

## Hyperedges (group relationships)
- **Provider-neutral Voice Turn Pipeline** — session_voice_session, contracts_provider_protocols, resilience_provider_failover, tools_tool_registry, session_rag_guard [EXTRACTED 1.00]
- **Tenant Agent Version Management Flow** — routes_agent_version_lifecycle, repository_postgres_rls, schemas_api_contracts, test_agent_versions_acceptance [INFERRED 0.95]
- **Phase 0 Local Acceptance Stack** — compose_local_platform, phase_0_local_acceptance, test_auth_flow_acceptance, test_rls_acceptance, smoke_local_stack [EXTRACTED 1.00]

## Communities (58 total, 23 thin omitted)

### Community 0 - "Voice Core Modules"
Cohesion: 0.09
Nodes (35): Protocol, RuntimeError, prompt(), test_backchannel_does_not_interrupt(), test_barge_in_cancels_speech_and_emits_event(), test_prompt_rejects_tenant_prompt_over_limit(), test_prompt_renders_context_and_rules(), test_session_executes_tool_and_continues() (+27 more)

### Community 1 - "API Authentication Routes"
Cohesion: 0.06
Nodes (15): Exercise agent draft, publish, version history and rollback against PostgreSQL., request(), headers(), HealthyChecker, test_agent_draft_versions_and_rollback(), test_agent_publish_session_and_isolation(), test_invalid_token_and_wrong_tenant(), test_operator_cannot_create_agent() (+7 more)

### Community 2 - "Memory Repository Operations"
Cohesion: 0.11
Nodes (3): MemoryRepository, PostgresRepository, tenant_session()

### Community 3 - "VoiceOS Platform Architecture"
Cohesion: 0.06
Nodes (34): AWS sa-east-1 Data Plane, LiveKit-based Voice Stack, Python 3.12 Backend, VoiceOS Multi-tenant Voice Agent Platform, Multi-tenancy, Tenant RBAC, RNF-06 Tenant Data Isolation, Agent Worker (+26 more)

### Community 4 - "Database Repository Layer"
Cohesion: 0.08
Nodes (3): Repository, MemoryStore, Deterministic dev adapter. Production endpoints use the same contract with Postg

### Community 5 - "API Schemas and Mock"
Cohesion: 0.11
Nodes (14): BaseModel, EmailMessage, test_tool_name_contract(), AgentCreate, AgentDraftPatch, AgentPatch, AgentRollback, CallEvent (+6 more)

### Community 6 - "Health Checks"
Cohesion: 0.16
Nodes (10): BaseSettings, FakeConnection, FakeConnectionContext, FakeEngine, FakeRedis, test_deep_health_success(), test_health_factory(), Settings (+2 more)

### Community 7 - "Backend Design Rationale"
Cohesion: 0.11
Nodes (21): immutable agent publish flow, Auth.js PostgreSQL schema, asynchronous database session factory, idempotent development seed, internal API token authentication, MemoryRepository, MemoryStore, VoiceOS NextAuth configuration (+13 more)

### Community 8 - "Phase Zero Architecture"
Cohesion: 0.1
Nodes (21): Auth.js Resend and Google Providers, JWT Tenant Principal Authentication, Auth.js PostgreSQL Session Store, Seven-service Local VoiceOS Platform, Database and Redis Health Check, FastAPI Error and Request-ID Boundary, Protected Tenant Dashboard Middleware, Forced Row Level Security Migration (+13 more)

### Community 9 - "Voice Runtime Concepts"
Cohesion: 0.12
Nodes (20): Voice Worker Simulation API, Agent Worker Drain State, LLM Response and Tool Call Contracts, Voice Provider Protocols, Agent Worker HTTP Server, Phase 0 AWS Staging Credential Gate, Sandboxed Contextual System Prompt, AWS sa-east-1 and GitHub OIDC Setup (+12 more)

### Community 10 - "Provider Resilience"
Cohesion: 0.22
Nodes (7): StrEnum, test_circuit_breaker_opens_and_half_opens(), test_resilient_call_retries_then_falls_back(), CircuitBreaker, CircuitOpenError, CircuitState, resilient_call()

### Community 11 - "Generated Runtime Contracts"
Cohesion: 0.29
Nodes (7): Generated OpenAPI TypeScript contract, Phase 1 voice runtime, RuntimeConfig, Tool and internal runtime test, API smoke health check, Tool name validation test, Typed provider adapters

### Community 14 - "Migration Tests"
Cohesion: 0.7
Nodes (4): load_initial_migration(), test_every_tenant_table_has_rls_contract(), test_join_tables_have_one_primary_key_and_unique_scope(), test_required_phase_zero_tables_exist()

### Community 15 - "Tenant Isolation Foundation"
Cohesion: 0.4
Nodes (5): Agent publish, session and isolation test, Migration and RLS contract tests, Phase 0 platform foundation, SQL-first exhaustive migration, Tenant-scoped row-level security

### Community 16 - "Web Dashboard Pages"
Cohesion: 0.5
Nodes (5): Tenant dashboard, emailLogin, googleLogin, Home, Login

### Community 21 - "RLS Acceptance Test"
Cohesion: 0.67
Nodes (3): main(), Real PostgreSQL RLS acceptance check for tenants, agents and calls., visible_count()

### Community 24 - "Background Worker Phases"
Cohesion: 0.67
Nodes (3): run worker loop, Local Docker Compose stack, Phase 4 WhatsApp processing

## Knowledge Gaps
- **79 isolated node(s):** `WorkerState`, `Complete VoiceOS v1 schema and tenant isolation.`, `Auth.js PostgreSQL adapter tables.`, `Idempotent PostgreSQL development seed.`, `Deterministic dev adapter. Production endpoints use the same contract with Postg` (+74 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Repository` connect `Database Repository Layer` to `Voice Core Modules`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `VoiceSession` connect `Voice Core Modules` to `Provider Resilience`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `MemoryRepository` connect `Memory Repository Operations` to `API Authentication Routes`, `Database Repository Layer`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `VoiceSession` (e.g. with `WorkerState` and `SimulationRequest`) actually correct?**
  _`VoiceSession` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `ToolRegistry` (e.g. with `WorkerState` and `SimulationRequest`) actually correct?**
  _`ToolRegistry` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `MemoryRepository` (e.g. with `MemoryStore` and `HealthyChecker`) actually correct?**
  _`MemoryRepository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `WorkerState`, `Complete VoiceOS v1 schema and tenant isolation.`, `Auth.js PostgreSQL adapter tables.` to the rest of the system?**
  _79 weakly-connected nodes found - possible documentation gaps or missing edges._