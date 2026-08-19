# 12 — Observabilidade

## Stack
OpenTelemetry SDK (Python e Node) → OTLP → Grafana Cloud (Loki logs, Prometheus/Mimir métricas, Tempo traces). Sentry para exceções em `web`, `api`, `agent-worker`, `worker`.

## Logs
JSON estruturado. Campos obrigatórios: `ts`, `level`, `service`, `env`, `request_id`/`call_id`, `tenant_id`, `msg`. Sem PII (`11`). Nível `debug` só em dev.

## Traces
- Span por request HTTP (`api`), por job (`worker`), por chamada (`agent-worker`: root span `call` com atributos `tenant_id, agent_id, channel`).
- Spans do pipeline por turno: `turn`, `stt.final`, `turn.detect`, `rag.query`, `llm.ttft`, `llm.total`, `tool.execute` (attr `tool_name`), `tts.ttfb`, `barge_in`.
- Propagar `traceparent` do `agent-worker` para a `api` em `/internal/*`.

## Métricas (Prometheus)
| métrica | tipo | labels |
|---|---|---|
| `voiceos_calls_active` | gauge | tenant, channel |
| `voiceos_calls_total` | counter | tenant, channel, status, end_reason |
| `voiceos_turn_ttfb_ms` | histogram | channel, provider_llm |
| `voiceos_stage_latency_ms` | histogram | stage (stt, turn, rag, llm_ttft, tts_ttfb) |
| `voiceos_barge_in_total` | counter | tenant |
| `voiceos_provider_errors_total` | counter | provider, kind |
| `voiceos_provider_fallback_total` | counter | from, to |
| `voiceos_tool_duration_ms` | histogram | tool_type, status |
| `voiceos_worker_rooms` | gauge | instance |
| `voiceos_cost_usd_total` | counter | tenant, component |
| `voiceos_http_requests_total`, `_duration_ms` | | route, status |
| `voiceos_jobs_total`, `_duration_ms` | | job, status |

## Dashboards (Grafana, provisionados por código em `infra/grafana/`)
1. **Overview**: chamadas ativas, chamadas/h, TTFB p50/p95, erros por provider, custo/h.
2. **Pipeline**: latência por estágio, barge-ins, fallbacks, STT reconnects.
3. **Tenant** (variável tenant): uso, custo, resolução, transferências.
4. **Infra**: CPU/mem por serviço, salas por worker, fila arq, Postgres conexões, Redis.

## Alertas (Grafana → Slack/e-mail/PagerDuty)
| alerta | condição |
|---|---|
| TTFB alto | p95 > 2.500 ms por 10 min |
| Erros de provider | > 5%/5 min em qualquer provider |
| Fallback ativo | fallback_total > 0 por 15 min |
| Chamadas falhando | `status=failed` > 3%/10 min |
| Worker saturado | rooms/instance ≥ 9 por 5 min (autoscale deve reagir; alerta se não) |
| Fila atrasada | job pendente > 5 min |
| API 5xx | > 1%/5 min |
| Twilio/LiveKit webhook silencioso | nenhum evento em 30 min com chamadas ativas |
| Custo anômalo | custo/h > 2× média 7 dias |
| Certificado/domínio | expira < 14 dias |

## Health checks
`GET /health` (api): DB, Redis, S3, LiveKit token. `GET /health` (agent-worker:8081): providers configurados, salas ativas, versão. `GET /ready` para ECS.

## Auditoria de conversa (produto)
Cada chamada tem trace id visível no painel (`/calls/[id]` → "detalhes técnicos"), permitindo suporte cruzar com Tempo.
