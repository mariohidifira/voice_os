# Graph Report - .  (2026-08-18)

## Corpus Check
- Corpus is ~21,432 words - fits in a single context window. You may not need a graph.

## Summary
- 235 nodes · 235 edges · 29 communities detected
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_API Core Services|API Core Services]]
- [[_COMMUNITY_Data Repository Layer|Data Repository Layer]]
- [[_COMMUNITY_Multi Tenant Architecture|Multi Tenant Architecture]]
- [[_COMMUNITY_Platform Design Decisions|Platform Design Decisions]]
- [[_COMMUNITY_Shared Data Contracts|Shared Data Contracts]]
- [[_COMMUNITY_Repository Operations|Repository Operations]]
- [[_COMMUNITY_Cloud Voice Platform|Cloud Voice Platform]]
- [[_COMMUNITY_OpenAPI Runtime Contracts|OpenAPI Runtime Contracts]]
- [[_COMMUNITY_Web Widget SDK|Web Widget SDK]]
- [[_COMMUNITY_Alembic Migration Runtime|Alembic Migration Runtime]]
- [[_COMMUNITY_Migration Contract Tests|Migration Contract Tests]]
- [[_COMMUNITY_Phase Zero Foundation|Phase Zero Foundation]]
- [[_COMMUNITY_Dashboard Authentication UI|Dashboard Authentication UI]]
- [[_COMMUNITY_Agent Worker Health|Agent Worker Health]]
- [[_COMMUNITY_Initial Database Schema|Initial Database Schema]]
- [[_COMMUNITY_Auth Database Schema|Auth Database Schema]]
- [[_COMMUNITY_Development Seed Data|Development Seed Data]]
- [[_COMMUNITY_Async Worker Stack|Async Worker Stack]]
- [[_COMMUNITY_API Package Metadata|API Package Metadata]]
- [[_COMMUNITY_Graceful Worker Shutdown|Graceful Worker Shutdown]]
- [[_COMMUNITY_API Observability Stack|API Observability Stack]]
- [[_COMMUNITY_Embeddable Voice Widget|Embeddable Voice Widget]]
- [[_COMMUNITY_Authorization Error Contracts|Authorization Error Contracts]]
- [[_COMMUNITY_Async Alembic Dispatch|Async Alembic Dispatch]]
- [[_COMMUNITY_Tool Schema Validation|Tool Schema Validation]]
- [[_COMMUNITY_Portuguese Application Layout|Portuguese Application Layout]]
- [[_COMMUNITY_Telephony Phase Two|Telephony Phase Two]]
- [[_COMMUNITY_Billing Governance Phase|Billing Governance Phase]]
- [[_COMMUNITY_Auth HTTP Handlers|Auth HTTP Handlers]]

## God Nodes (most connected - your core abstractions)
1. `Repository` - 11 edges
2. `MemoryRepository` - 11 edges
3. `PostgresRepository` - 10 edges
4. `get_settings()` - 8 edges
5. `tenant_session()` - 8 edges
6. `MemoryStore` - 7 edges
7. `LGPD Compliance Program` - 6 edges
8. `VoiceOSWidget` - 5 edges
9. `headers()` - 5 edges
10. `Streaming Voice Pipeline` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Agent publish, session and isolation test` --validates_tenant_isolation_behavior--> `Tenant-scoped row-level security`  [INFERRED]
  tests/test_api.py → PHASE-0-REPORT.md
- `Phase 4 WhatsApp processing` --uses_async_worker_boundary--> `run worker loop`  [INFERRED]
  PHASE-4-REPORT.md → apps/worker/main.py
- `test_invalid_token_and_wrong_tenant()` --calls--> `get_settings()`  [INFERRED]
  tests/test_api.py → apps/api/voiceos_api/config.py
- `Migration and RLS contract tests` --validates_schema_scope--> `Tenant-scoped row-level security`  [EXTRACTED]
  tests/test_migrations.py → PHASE-0-REPORT.md
- `Phase 1 voice runtime` --defines_typed_contracts_for--> `RuntimeConfig`  [EXTRACTED]
  PHASE-1-REPORT.md → packages/shared-py/voiceos_shared/contracts.py

## Hyperedges (group relationships)
- **defense-in-depth tenant isolation** — principal_auth, principal, tenant_session, tenant_rls [INFERRED 0.95]
- **voice session provisioning flow** — session_creation, repository_contract, settings, runtime_endpoint, worker_main [INFERRED 0.85]
- **shared repository adapter contract** — repository_contract, postgres_repository, memory_repository, memory_store [EXTRACTED 1.00]
- **Web authentication to tenant dashboard flow** —  [EXTRACTED 1.00]
- **Tenant safety verification** —  [INFERRED 0.95]
- **Real-time Voice Conversation Flow** — 09_canais_omnichannel, 02_arquitetura_agent_worker, 05_voice_pipeline_streaming_pipeline, 06_tools_integracoes_tool_system [EXTRACTED 1.00]
- **Tenant Isolation Controls** — 01_visao_produto_multitenancy, 01_visao_produto_rbac, 01_visao_produto_rnf_isolamento, 03_modelo_dados_rls, 13_testes_aceite_quality_gates [INFERRED 0.95]
- **LGPD Governance Artifacts** — 11_seguranca_lgpd_compliance, dpa_controller_processor_roles, incident_lgpd_runbook, privacy_policy_data_subject_rights, subprocessors_provider_registry [EXTRACTED 1.00]

## Communities (46 total, 18 thin omitted)

### Community 0 - "API Core Services"
Cohesion: 0.08
Nodes (11): BaseSettings, headers(), test_agent_publish_session_and_isolation(), test_invalid_token_and_wrong_tenant(), test_operator_cannot_create_agent(), test_tool_and_internal_runtime(), internal_token(), Principal (+3 more)

### Community 1 - "Data Repository Layer"
Cohesion: 0.11
Nodes (5): MemoryRepository, PostgresRepository, tenant_session(), MemoryStore, Deterministic dev adapter. Production endpoints use the same contract with Postg

### Community 2 - "Multi Tenant Architecture"
Cohesion: 0.09
Nodes (24): Multi-tenancy, Tenant RBAC, RNF-06 Tenant Data Isolation, Agent Worker, Async Worker, VoiceOS Service Architecture, Immutable Published Agent Versions, PostgreSQL Tenant Data Model (+16 more)

### Community 3 - "Platform Design Decisions"
Cohesion: 0.11
Nodes (21): immutable agent publish flow, Auth.js PostgreSQL schema, asynchronous database session factory, idempotent development seed, internal API token authentication, MemoryRepository, MemoryStore, VoiceOS NextAuth configuration (+13 more)

### Community 4 - "Shared Data Contracts"
Cohesion: 0.17
Nodes (11): BaseModel, test_tool_name_contract(), AgentCreate, AgentPatch, CallEvent, SessionCreate, ToolCreate, ErrorBody (+3 more)

### Community 6 - "Cloud Voice Platform"
Cohesion: 0.2
Nodes (10): AWS sa-east-1 Data Plane, LiveKit-based Voice Stack, Python 3.12 Backend, VoiceOS Multi-tenant Voice Agent Platform, LGPD Compliance Program, Tenant Secret Encryption, Controller and Processor Roles, LGPD Incident Runbook (+2 more)

### Community 7 - "OpenAPI Runtime Contracts"
Cohesion: 0.29
Nodes (7): Generated OpenAPI TypeScript contract, Phase 1 voice runtime, RuntimeConfig, Tool and internal runtime test, API smoke health check, Tool name validation test, Typed provider adapters

### Community 10 - "Migration Contract Tests"
Cohesion: 0.7
Nodes (4): load_initial_migration(), test_every_tenant_table_has_rls_contract(), test_join_tables_have_one_primary_key_and_unique_scope(), test_required_phase_zero_tables_exist()

### Community 11 - "Phase Zero Foundation"
Cohesion: 0.4
Nodes (5): Agent publish, session and isolation test, Migration and RLS contract tests, Phase 0 platform foundation, SQL-first exhaustive migration, Tenant-scoped row-level security

### Community 12 - "Dashboard Authentication UI"
Cohesion: 0.5
Nodes (5): Tenant dashboard, emailLogin, googleLogin, Home, Login

### Community 19 - "Async Worker Stack"
Cohesion: 0.67
Nodes (3): run worker loop, Local Docker Compose stack, Phase 4 WhatsApp processing

## Knowledge Gaps
- **53 isolated node(s):** `WorkerState`, `Complete VoiceOS v1 schema and tenant isolation.`, `Auth.js PostgreSQL adapter tables.`, `Idempotent PostgreSQL development seed.`, `Deterministic dev adapter. Production endpoints use the same contract with Postg` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Repository` connect `Repository Operations` to `Data Repository Layer`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `get_settings()` (e.g. with `Principal` and `internal_token()`) actually correct?**
  _`get_settings()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `WorkerState`, `Complete VoiceOS v1 schema and tenant isolation.`, `Auth.js PostgreSQL adapter tables.` to the rest of the system?**
  _53 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `API Core Services` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Data Repository Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Should `Multi Tenant Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._
- **Should `Platform Design Decisions` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._