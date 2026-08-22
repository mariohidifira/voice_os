# Graph Report - VOICE_OS  (2026-08-22)

## Corpus Check
- 183 files · ~116,395 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1737 nodes · 4260 edges · 131 communities (95 shown, 36 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 386 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `25b6e356`
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
- routes.py
- ._internal_session
- MemoryStore
- evaluate
- LiveKitCallBridge
- WorkerAPI
- FakeEventBus
- repository.py
- CallAccounting
- get_agent
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
- test_tool
- Repository protocol
- __init__.py
- .get_agent
- LastOwnerError
- RedisRuntimeCache
- .get_tenant
- TelephonyProviderError
- FakeEventBus
- FakeVoicePreview
- test_phone_numbers.py
- SessionGuards
- SipDispatch
- auth.py
- .get_tenant
- prompt_improvement.py
- date
- ToolCall
- VoiceSession
- add_campaign_contacts
- run_case
- livekit_sessions.py
- create_agent
- NumberProvider
- test_billing.py
- admin-dashboard.tsx
- RedisRuntimeCache
- build_system_prompt
- FakeEventBus
- get_export
- retention_tick

## God Nodes (most connected - your core abstractions)
1. `MemoryRepository` - 131 edges
2. `Repository` - 124 edges
3. `PostgresRepository` - 124 edges
4. `Settings` - 63 edges
5. `get_settings()` - 63 edges
6. `_require_admin()` - 50 edges
7. `VoiceSession` - 37 edges
8. `WorkerAPI` - 33 edges
9. `ToolRegistry` - 30 edges
10. `LLMResponse` - 28 edges

## Surprising Connections (you probably didn't know these)
- `test_egress_webhook_maps_completed_file_to_recording()` --calls--> `_egress_recording()`  [INFERRED]
  tests/test_recording.py → apps/api/voiceos_api/routes.py
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

## Communities (131 total, 36 thin omitted)

### Community 0 - "Voice Core Modules"
Cohesion: 0.21
Nodes (24): BaseModel, simulate(), SimulationRequest, SimulationResponse, WorkerState, LLMResponse, MockLLM, MockRAG (+16 more)

### Community 1 - "API Authentication Routes"
Cohesion: 0.14
Nodes (10): ElevenLabsVoicePreview, get_voice_preview(), Any, AsyncBaseTransport, Protocol, Response, UnavailableVoicePreview, VoicePreview (+2 more)

### Community 3 - "VoiceOS Platform Architecture"
Cohesion: 0.06
Nodes (34): AWS sa-east-1 Data Plane, LiveKit-based Voice Stack, Python 3.12 Backend, VoiceOS Multi-tenant Voice Agent Platform, Six-phase Delivery Roadmap, Controller and Processor Roles, LGPD Incident Runbook, VoiceOS Subprocessor Registry (+26 more)

### Community 4 - "Database Repository Layer"
Cohesion: 0.04
Nodes (47): dependencies, @auth/core, @auth/pg-adapter, livekit-client, next, next-auth, pg, react (+39 more)

### Community 5 - "API Schemas and Mock"
Cohesion: 0.11
Nodes (48): admin_impersonate(), admin_metrics(), admin_tenants(), admin_update_tenant(), billing_checkout(), billing_invoices(), billing_meter_tick(), billing_plan() (+40 more)

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
Cohesion: 0.07
Nodes (20): GET(), proxy(), createWorkspace(), databaseUrl, emailProvider, providers, secureCookies, databaseUrl (+12 more)

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
Cohesion: 0.09
Nodes (17): AgentTab, agentTabs, AgentTemplate, api(), AvailableNumber, BillingPlan, BillingUsage, Call (+9 more)

### Community 33 - "Job Worker"
Cohesion: 0.50
Nodes (7): billing_meter(), campaign_runner(), export_runner(), AsyncClient, retention_runner(), run(), webhook_runner()

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
Cohesion: 0.19
Nodes (10): Settings, ExportStorage, get_export_storage(), get_recording_storage(), get_retention_storage(), Any, RecordingStorage, RetentionStorage (+2 more)

### Community 41 - "ESLint Configuration"
Cohesion: 0.33
Nodes (5): Como usar este pacote, Decisões fechadas (não reabrir), Especificação Técnica — Plataforma de Agentes de Voz Multi-tenant, Regras para o agente executor, Índice

### Community 42 - "Next Type Declarations"
Cohesion: 0.50
Nodes (3): compat, config, directory

### Community 63 - "Any"
Cohesion: 0.04
Nodes (3): Protocol, UUID, Repository

### Community 64 - "PostgresRepository"
Cohesion: 0.05
Nodes (9): immutable agent publish flow, PostgresRepository, tenant_session(), test_postgres_agent_and_call_lifecycle(), test_postgres_billing_usage_subscription_and_invoice_reconcile(), test_postgres_campaign_claim_and_result_reconciliation(), test_postgres_members_and_api_keys_lifecycle(), test_postgres_phase3_webhooks_exports_and_lgpd() (+1 more)

### Community 65 - "knowledge.py"
Cohesion: 0.17
Nodes (9): chunk_text(), Embeddings, extract_bytes(), get_embeddings(), AsyncBaseTransport, _TextExtractor, HTMLParser, test_chunk_text_respects_overlap_and_boundaries() (+1 more)

### Community 66 - "get_settings"
Cohesion: 0.11
Nodes (21): FakePromptImprover, FakeRecordingStorage, FakeVoicePreview, headers(), HealthyChecker, test_agent_draft_versions_and_rollback(), test_agent_publish_session_and_isolation(), test_call_lifecycle_internal_batches_and_detail() (+13 more)

### Community 67 - "test_health.py"
Cohesion: 0.15
Nodes (10): HealthChecker, Any, FakeConnection, FakeConnectionContext, FakeEngine, FakeRedis, Any, MonkeyPatch (+2 more)

### Community 68 - "tool_execution.py"
Cohesion: 0.23
Nodes (12): get_tool_executor(), _json_path(), _lookup(), Any, AsyncBaseTransport, _render(), _safe_url(), ToolExecutor (+4 more)

### Community 69 - "routes.py"
Cohesion: 0.10
Nodes (52): add_do_not_call(), create_export(), create_internal_call(), AdminTenantPatch, AgentCreate, AgentDraftPatch, AgentPatch, AgentRollback (+44 more)

### Community 71 - "MemoryStore"
Cohesion: 0.19
Nodes (15): AgentSession, dynamic_tools(), provider_pipeline(), Any, UUID, room_metadata(), send_dtmf(), transfer_phone_call() (+7 more)

### Community 72 - "evaluate"
Cohesion: 0.29
Nodes (12): evaluate(), fetch_calls(), main(), percentile(), Any, Verify Phase 1 media acceptance from real staging call records., acceptance_calls(), Any (+4 more)

### Community 73 - "LiveKitCallBridge"
Cohesion: 0.14
Nodes (18): VoiceOS FastAPI application, AsyncSession, session(), get_health_checker(), health(), http_error(), Any, HTTPException (+10 more)

### Community 74 - "WorkerAPI"
Cohesion: 0.22
Nodes (6): Any, AsyncBaseTransport, Protocol, UUID, RuntimeCache, WorkerAPI

### Community 76 - "FakeEventBus"
Cohesion: 0.26
Nodes (10): internal_token(), Principal, Header, UUID, get_settings(), internal_request(), Any, Exercise agent draft, publish, version history and rollback against PostgreSQL. (+2 more)

### Community 77 - "repository.py"
Cohesion: 0.17
Nodes (14): LLMProvider, Any, Protocol, RAGProvider, STTProvider, TTSProvider, VoiceEvent, Provider-neutral VoiceOS realtime conversation core. (+6 more)

### Community 78 - "CallAccounting"
Cohesion: 0.17
Nodes (9): CallAccounting, estimate_mos(), _percentile(), Any, MetricsCollectedEvent, SessionUsageUpdatedEvent, _rate(), test_accounting_aggregates_latency_usage_and_cost() (+1 more)

### Community 79 - "get_agent"
Cohesion: 0.15
Nodes (29): alias, analytics_overview(), analytics_tools(), assign_phone_number(), available_phone_numbers(), billing_usage(), calls(), campaign_runner_tick() (+21 more)

### Community 80 - "MemoryRuntimeCache"
Cohesion: 0.22
Nodes (10): MemoryRuntimeCache, dial_outbound(), MonkeyPatch, test_dial_outbound_maps_sip_lifecycle(), test_dial_outbound_records_provider_failure(), test_dynamic_tools_mutate_variables_and_proxy_remote_execution(), test_transfer_native_tool_summarizes_and_closes(), test_transfer_phone_call_supports_cold_and_warm() (+2 more)

### Community 81 - "RuntimeCache"
Cohesion: 0.05
Nodes (45): EgressStarter, Protocol, UUID, start_egress(), start_room_recording(), dialing_allowed(), Any, datetime (+37 more)

### Community 82 - "livekit_sessions.py"
Cohesion: 0.13
Nodes (12): DevSipDispatch, DevSipOutbound, get_telephony(), LiveKitSipDispatch, LiveKitSipOutbound, RuntimeError, UUID, Raised when a provider operation cannot be completed safely. (+4 more)

### Community 89 - "repository.py"
Cohesion: 0.11
Nodes (41): transition_status(), extract_url(), append_call_events(), append_call_tool_call(), append_call_turns(), campaign_action(), create_document(), delete_agent() (+33 more)

### Community 90 - "RedisRuntimeCache"
Cohesion: 0.15
Nodes (6): DevStripeGateway, get_stripe_gateway(), Any, Protocol, StripeGateway, StripeHTTPGateway

### Community 91 - "test_tool"
Cohesion: 0.25
Nodes (11): execute_tool(), get_tool(), google_callback(), google_connect(), outgoing_webhook_tick(), _resolve_tool_secret(), test_tool(), update_tool() (+3 more)

### Community 92 - "Repository protocol"
Cohesion: 0.22
Nodes (8): AnthropicPostprocessor, get_postprocessor(), Postprocessor, Any, AsyncBaseTransport, Protocol, test_postprocessor_retries_invalid_provider_response(), test_postprocessor_sends_transcript_and_validates_structured_result()

### Community 97 - ".get_agent"
Cohesion: 0.18
Nodes (8): get_idempotency_store(), IdempotencyStore, MemoryIdempotencyStore, Any, Protocol, UUID, RedisIdempotencyStore, test_redis_idempotency_reserves_replays_rejects_and_releases()

### Community 98 - "LastOwnerError"
Cohesion: 0.19
Nodes (9): _jsonable(), LiveKitCallBridge, MetricsCollectedEvent, SessionUsageUpdatedEvent, CloseEvent, ConversationItemAddedEvent, test_call_bridge_persists_final_transcript_and_closes_call(), test_call_bridge_uses_livekit_end_to_end_voice_latency() (+1 more)

### Community 99 - "RedisRuntimeCache"
Cohesion: 0.14
Nodes (18): delivery_result(), OutgoingWebhookSender, Any, AsyncClient, webhook_signature(), Processor, auth(), FakeExportStorage (+10 more)

### Community 101 - ".get_tenant"
Cohesion: 0.16
Nodes (10): AMDClassifier, AnthropicAMDClassifier, business_hours_open(), HeuristicAMDClassifier, AsyncBaseTransport, datetime, Protocol, test_amd_heuristics_distinguish_human_voicemail_and_ivr() (+2 more)

### Community 102 - "TelephonyProviderError"
Cohesion: 0.43
Nodes (6): email(), EmailMessage, get_last_email(), health(), BaseModel, tool()

### Community 104 - "FakeEventBus"
Cohesion: 0.50
Nodes (4): list_voices(), preview_voice(), Response, Voice

### Community 106 - "test_phone_numbers.py"
Cohesion: 0.35
Nodes (8): auth(), UUID, reset(), test_outbound_call_is_tenant_scoped_and_idempotent(), test_outbound_requires_sip_dialer_configuration(), test_phone_number_search_purchase_assignment_release_and_isolation(), test_phone_purchase_compensates_when_sip_dispatch_fails(), TrackingDispatch

### Community 107 - "SessionGuards"
Cohesion: 0.38
Nodes (3): SessionGuards, test_session_guards_prompt_once_then_end_after_second_silence(), UserStateChangedEvent

### Community 108 - "SipDispatch"
Cohesion: 0.17
Nodes (10): CircuitBreaker, CircuitOpenError, CircuitState, RuntimeError, resilient_call(), StrEnum, T, test_deepgram_key_chaos_activates_fallback_with_alert_rule() (+2 more)

### Community 109 - "auth.py"
Cohesion: 0.47
Nodes (5): main(), Any, AsyncClient, Synchronize VoiceOS plans and recurring/metered prices with Stripe., stripe_post()

### Community 110 - ".get_tenant"
Cohesion: 0.15
Nodes (7): DevNumberProvider, PurchasedNumber, Any, AsyncBaseTransport, Response, TwilioNumberProvider, test_twilio_number_provider_uses_official_inventory_and_purchase_contracts()

### Community 113 - "prompt_improvement.py"
Cohesion: 0.20
Nodes (8): AnthropicPromptImprover, get_prompt_improver(), PromptImprover, AsyncBaseTransport, Protocol, UnavailablePromptImprover, test_prompt_improver_preserves_jinja_variables(), test_prompt_improver_retries_when_provider_drops_variable()

### Community 115 - "ToolCall"
Cohesion: 0.25
Nodes (5): ToolCall, MockSTT, tool(), Any, ToolHandler

### Community 117 - "add_campaign_contacts"
Cohesion: 0.18
Nodes (11): stripe_event(), stripe_signature_valid(), add_campaign_contacts(), _egress_recording(), list_do_not_call(), livekit_webhook(), datetime, Request (+3 more)

### Community 118 - "run_case"
Cohesion: 0.36
Nodes (9): CaseResult, load_cases(), main(), Any, Deterministic conversation acceptance runner for PR (text) and nightly (audio)., run_case(), run_suite(), test_conversation_acceptance_suite() (+1 more)

### Community 119 - "livekit_sessions.py"
Cohesion: 0.27
Nodes (5): get_livekit_sessions(), LiveKitSessions, Any, UUID, test_dev_session_token_contains_room_and_publish_grants()

### Community 120 - "create_agent"
Cohesion: 0.25
Nodes (8): get_agent_template(), list_agent_templates(), Any, agent_templates(), create_agent(), _enforce_agent_limit(), list_agents(), update_draft()

### Community 121 - "NumberProvider"
Cohesion: 0.22
Nodes (4): NumberProvider, Protocol, SipDispatch, SipOutbound

### Community 122 - "test_billing.py"
Cohesion: 0.50
Nodes (7): auth(), UUID, reset(), test_billing_plan_usage_checkout_portal_and_limits(), test_hourly_meter_reports_only_overage_and_marks_records(), test_stripe_signature_verification(), test_stripe_webhook_updates_subscription_invoice_and_tenant()

### Community 123 - "admin-dashboard.tsx"
Cohesion: 0.40
Nodes (3): AdminDashboard(), request(), Tenant

### Community 125 - "build_system_prompt"
Cohesion: 0.50
Nodes (4): build_system_prompt(), Any, datetime, test_prompt_rejects_tenant_prompt_over_limit()

### Community 128 - "get_export"
Cohesion: 0.67
Nodes (3): export_tick(), get_export(), ExportStore

## Knowledge Gaps
- **193 isolated node(s):** `Tenant`, `Item`, `Call`, `Document`, `AgentTemplate` (+188 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Repository` connect `Any` to `Memory Repository Operations`, `routes.py`, `repository.py`, `get_agent`, `RuntimeCache`, `date`, `create_agent`, `repository.py`, `test_tool`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `voiceos_agent()` connect `MemoryStore` to `LastOwnerError`, `.get_tenant`, `FakeVoicePreview`, `WorkerAPI`, `SessionGuards`, `MemoryRuntimeCache`, `RuntimeCache`, `RedisRuntimeCache`, `build_system_prompt`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `MemoryRepository` connect `Memory Repository Operations` to `PostgresRepository`, `get_settings`, `RedisRuntimeCache`, `._internal_session`, `TwilioNumberProvider`, `Backend Design Rationale`, `test_phone_numbers.py`, `RuntimeCache`, `date`, `livekit_sessions.py`, `FakeEventBus`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `MemoryRepository` (e.g. with `MemoryStore` and `HealthyChecker`) actually correct?**
  _`MemoryRepository` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Repository` (e.g. with `NativeIntegrations` and `MemoryStore`) actually correct?**
  _`Repository` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `PostgresRepository` (e.g. with `MemoryRepository` and `MemoryStore`) actually correct?**
  _`PostgresRepository` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tenant`, `Item`, `Call` to the rest of the system?**
  _193 weakly-connected nodes found - possible documentation gaps or missing edges._