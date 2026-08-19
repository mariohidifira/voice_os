# 13 — Testes e Critérios de Aceite

## Pirâmide
| Camada | Ferramenta | Cobertura |
|---|---|---|
| Unit (backend) | pytest, pytest-asyncio, factory_boy | ≥ 80% linhas; 100% em billing, RLS, tool executor, template renderer |
| Unit (frontend) | Vitest + Testing Library | componentes de formulário e RBAC |
| Integração API | pytest + httpx contra Postgres/Redis reais (docker) | todos os endpoints `/v1` e `/internal` |
| Contrato | schemathesis contra OpenAPI | rotas públicas |
| E2E painel | Playwright | onboarding, criar agente, publicar, testar no widget, comprar número (mock Twilio), ver chamada, billing checkout (Stripe test) |
| Pipeline de voz | suíte de conversas simuladas (abaixo) | por PR em modo curto (10 casos), nightly completo (100+) |
| Carga | k6 (API) + simulador de salas (LiveKit CLI `lk load-test` + agente) | antes de cada fase ≥ 2 |
| Segurança | testes de isolamento RLS, SSRF, injeção de prompt, auth | por PR |

## Suíte de conversas simuladas (`tests/conversations/`)
Formato YAML por caso:
```yaml
id: faq_horario
agent_template: recepcionista
kb: fixtures/kb_clinica.md
channel: web
turns:
  - user: "Oi, vocês abrem no sábado?"
    expect:
      contains_any: ["sábado", "não abrimos", "abrimos"]
      max_ttfb_ms: 1500
      no_tool: true
  - user: "Então quero marcar para segunda de manhã"
    expect:
      tool_called: google_calendar_check
      tool_args_match: { date: "*segunda*|*monday*|20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]" }
interruptions:
  - at_turn: 2
    after_ms: 800
    user: "não, terça"
    expect:
      agent_stops_within_ms: 300
      history_truncated: true
```
Runner: sobe sessão real com TTS sintético do "usuário" (voz diferente) injetado como track na room, ou modo texto (bypass STT/TTS) para velocidade. Ambos os modos existem: `--mode text` (PR), `--mode audio` (nightly).

Casos obrigatórios (mínimo 40) cobrindo: saudação, FAQ via KB, KB sem resposta (não inventa), cada tool nativa, tool webhook ok/erro/timeout, barge-in cedo/tarde, backchannel ignorado, troca de assunto, coleta de variáveis, confirmação antes de ação, pedido de humano, silêncio, encerramento, injeção de prompt via KB e via tool result, números/datas por extenso, fora do horário, outbound saudação, voicemail, opt-out.

Métricas do nightly viram relatório: taxa de aprovação, TTFB p50/p95, custo médio. Falha se aprovação < 95% ou TTFB p95 > RNF-02.

## Testes de carga
- API: 200 rps mistas por 10 min, p95 < 300 ms, 0 erros 5xx.
- Voz: 50 salas simultâneas com agente respondendo por 5 min: TTFB p95 dentro do RNF, sem sala derrubada, autoscale de `agent-worker` observado.

## Testes de isolamento
Para cada tabela com `tenant_id`: criar dados em 2 tenants, autenticar como tenant A, tentar ler/alterar B por id → 404. Executado por PR.

## Critérios de aceite gerais (aplicam a toda fase)
- CI verde (lint, types, testes, cobertura).
- `PHASE-N-REPORT.md` escrito.
- Deploy em staging feito e smoke test (script `make smoke`) passando.
- Nenhum TODO crítico aberto; itens fora do escopo listados no report.
