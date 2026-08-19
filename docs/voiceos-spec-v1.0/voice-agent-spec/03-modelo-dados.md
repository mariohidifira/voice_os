# 03 — Modelo de Dados (PostgreSQL 16)

Convenções: `id UUID DEFAULT gen_random_uuid()`, `created_at/updated_at TIMESTAMPTZ`, `tenant_id` em toda tabela de domínio, soft delete via `deleted_at` onde indicado. Enums como `TEXT` com `CHECK`. Migrações com Alembic, uma por PR. Nomes em inglês, snake_case.

## Diagrama (resumo)

```
tenants 1─n users(memberships) 
tenants 1─n agents 1─n agent_versions
agents 1─n phone_numbers
agents 1─n knowledge_bases 1─n documents 1─n chunks(vector)
tenants 1─n tools ; agents n─n tools (agent_tools)
agents 1─n calls 1─n call_turns / call_events / call_tool_calls
calls 1─1 call_recordings ; calls 1─1 call_qa
tenants 1─n api_keys ; tenants 1─n webhooks_out
tenants 1─1 subscriptions 1─n usage_records ; invoices
tenants 1─n campaigns 1─n campaign_contacts
tenants 1─n secrets
tenants 1─n end_users
```

## Tabelas

### tenants
| coluna | tipo | notas |
|---|---|---|
| id | uuid pk | |
| slug | text unique | usado em URLs e subdomínio |
| name | text | |
| status | text | `active` `suspended` `trial` `cancelled` |
| plan_id | uuid fk plans | |
| settings | jsonb | timezone, locale, retention_days (default 90), recording_enabled, branding |
| stripe_customer_id | text | |
| created_at, updated_at, deleted_at | | |

### users
| id | uuid pk |
| email | text unique |
| name | text |
| avatar_url | text |
| is_platform_admin | bool | agência |
| last_login_at | timestamptz |

### memberships
| user_id fk | tenant_id fk | role text `owner` `admin` `operator` `viewer` | pk (user_id, tenant_id) |

### agents
| id | uuid | |
| tenant_id | uuid | |
| name | text | |
| status | text | `draft` `active` `paused` `archived` |
| current_version_id | uuid fk agent_versions | versão publicada |
| draft_version_id | uuid fk agent_versions | versão em edição |
| created_at, updated_at, deleted_at | | |

### agent_versions (imutáveis após publicar)
| id | uuid | |
| agent_id | uuid | |
| version | int | sequencial por agent |
| published_at | timestamptz null | |
| system_prompt | text | template com variáveis (`07-prompts.md`) |
| greeting | text | primeira fala; suporta variáveis |
| language | text | `pt-BR` default |
| extra_languages | text[] | |
| llm | jsonb | `{provider, model, temperature, max_tokens}` |
| stt | jsonb | `{provider, model, keywords[], endpointing_ms}` |
| tts | jsonb | `{provider, voice_id, speed, stability, style}` |
| turn | jsonb | `{min_endpointing_delay_ms, max_endpointing_delay_ms, allow_interruptions, interrupt_min_words}` |
| behavior | jsonb | `{max_call_duration_s, silence_timeout_s, silence_prompt, end_call_phrases[], filler_enabled, filler_phrases[], transfer_number, voicemail_message, business_hours{}, out_of_hours_message}` |
| knowledge_base_id | uuid null | |
| rag | jsonb | `{enabled, top_k, min_score, max_tokens}` |
| variables | jsonb | defaults de variáveis do prompt |
| created_by | uuid | |
| created_at | | |

### phone_numbers
| id | tenant_id | agent_id null | e164 text unique | provider `twilio` | provider_sid | capabilities jsonb `{voice, sms}` | status `active` `released` | livekit_dispatch_rule_id |

### knowledge_bases
| id | tenant_id | name | embedding_model text (`text-embedding-3-small`) | chunk_size int (800) | chunk_overlap int (120) | status |

### documents
| id | tenant_id | knowledge_base_id | name | source_type `upload` `url` `text` | source_uri | s3_key | mime | size_bytes | status `pending` `processing` `ready` `error` | error text | chunk_count | checksum | created_at |

### chunks
| id | tenant_id | document_id | knowledge_base_id | ordinal int | content text | embedding vector(1536) | metadata jsonb (`{page, heading, url}`) | token_count |
Índice: `CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)`; índice por `(knowledge_base_id)`.

### tools
| id | tenant_id | name text (snake_case, unique por tenant) | description text (para o LLM) | type `native` `webhook` | native_kind text null (`transfer_call`, `end_call`, `send_sms`, `send_email`, `google_calendar_check`, `google_calendar_book`, `set_variable`, `dtmf`) | parameters_schema jsonb (JSON Schema) | webhook jsonb `{url, method, headers{}, auth{type, secret_id}, timeout_ms, body_template, response_mapping}` | speak_before text null (fala enquanto executa) | async bool | created_at |

### agent_tools
| agent_version_id | tool_id | enabled bool | pk (agent_version_id, tool_id) |

### secrets
| id | tenant_id | name | ciphertext bytea | kms_key_id | created_at | rotated_at |

### end_users
| id | tenant_id | external_id text null | phone e164 null | email null | name null | metadata jsonb | first_seen_at | last_seen_at |
Unique por (tenant_id, external_id) e (tenant_id, phone).

### calls
| coluna | tipo | notas |
|---|---|---|
| id | uuid | |
| tenant_id, agent_id, agent_version_id | | |
| channel | text | `web` `phone_inbound` `phone_outbound` `whatsapp` |
| status | text | `queued` `ringing` `in_progress` `completed` `failed` `no_answer` `busy` `voicemail` `cancelled` |
| end_reason | text | `user_hangup` `agent_hangup` `transferred` `max_duration` `silence` `error` `voicemail_left` |
| end_user_id | uuid null | |
| from_number, to_number | text | |
| livekit_room | text | |
| provider_call_sid | text | Twilio CallSid |
| campaign_id | uuid null | |
| started_at, answered_at, ended_at | timestamptz | |
| duration_s | int | answered→ended |
| billable_seconds | int | |
| cost | jsonb | `{stt, llm, tts, telephony, livekit, total}` em USD |
| latency | jsonb | `{ttfb_p50_ms, ttfb_p95_ms, turns}` |
| summary | text | gerado pós-chamada |
| outcome | jsonb | `{resolved bool, transferred bool, tags[], sentiment}` |
| variables | jsonb | variáveis coletadas na conversa |
| metadata | jsonb | recebido na criação da sessão |
| created_at | | |
Índices: `(tenant_id, started_at desc)`, `(agent_id, started_at desc)`, `(end_user_id)`.

### call_turns
| id | tenant_id | call_id | ordinal | role `user` `agent` `system` | text | started_at | ended_at | interrupted bool | ttfb_ms int null (agent) | stt_confidence float null | audio_offset_ms int |

### call_tool_calls
| id | tenant_id | call_id | turn_id | tool_id | name | arguments jsonb | result jsonb | status `ok` `error` `timeout` | duration_ms | started_at |

### call_events
| id | tenant_id | call_id | type text | payload jsonb | at timestamptz |
Tipos: `call.started` `call.answered` `call.ended` `turn.user` `turn.agent` `barge_in` `tool.called` `tool.result` `transfer.requested` `transfer.completed` `error` `dtmf`.

### call_recordings
| call_id pk | tenant_id | s3_key | format `ogg` `mp3` | duration_s | size_bytes | expires_at | status |

### call_qa
| call_id pk | tenant_id | score int 0-100 | rubric jsonb | issues text[] | model | created_at |

### campaigns
| id | tenant_id | agent_id | name | status `draft` `scheduled` `running` `paused` `done` | schedule jsonb `{start_at, window_start "09:00", window_end "18:00", days[], timezone, max_concurrency, retry_policy{max_attempts, delay_min}}` | stats jsonb |

### campaign_contacts
| id | tenant_id | campaign_id | phone | name | variables jsonb | status `pending` `calling` `done` `failed` `no_answer` `retry` | attempts int | last_call_id | next_attempt_at |

### api_keys
| id | tenant_id | name | prefix text | hash text | scope text `public` `secret` | allowed_origins text[] | last_used_at | revoked_at |

### webhooks_out
| id | tenant_id | url | events text[] | secret_id | enabled | created_at |
### webhook_deliveries
| id | tenant_id | webhook_id | event | payload jsonb | status | attempts | last_status_code | next_retry_at |

### plans
| id | code text unique (`starter` `pro` `business` `enterprise`) | name | monthly_price_cents | included_minutes | overage_cents_per_min | max_agents | max_concurrent_calls | features jsonb | stripe_price_id |

### subscriptions
| id | tenant_id unique | plan_id | stripe_subscription_id | status | current_period_start | current_period_end | cancel_at |

### usage_records
| id | tenant_id | call_id | period (date, primeiro dia do mês) | billable_seconds | channel | cost_usd numeric | stripe_usage_record_id null | created_at |
Índice único `(call_id)`.

### invoices
| id | tenant_id | stripe_invoice_id | period_start | period_end | amount_cents | status | pdf_url |

### events (auditoria de negócio)
| id | tenant_id null | actor_type `user` `system` `api_key` | actor_id | type text | entity_type | entity_id | payload jsonb | at |

## Row Level Security
Habilitar RLS em toda tabela com `tenant_id`. Política:
```sql
CREATE POLICY tenant_isolation ON <table>
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```
A `api` faz `SET LOCAL app.tenant_id = '<uuid>'` no início de cada transação. Platform admin usa role `voiceos_admin` com `BYPASSRLS` apenas em endpoints `/admin/*`.

## Retenção e purga
Job diário no `worker`: apaga `call_recordings` com `expires_at < now()` (S3 + linha), anonimiza `call_turns.text` de chamadas mais antigas que `tenants.settings.retention_days` se `settings.anonymize_transcripts = true`, apaga `documents` com `deleted_at` > 30 dias.

## Seed de desenvolvimento
Script `make seed`: 1 tenant `demo`, 1 usuário owner, 1 agente `Recepcionista` com prompt padrão, 1 KB com 3 documentos, 2 tools (webhook fake em `http://mock:9000` e `transfer_call`), 20 chamadas fake com turns.
