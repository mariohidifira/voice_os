# Relatório da Fase 2 — Telefone

Status: **em implementação**. Dependências de provedores estão **pendentes e não bloqueantes para o desenvolvimento local**. Nenhum aceite que exija Twilio/LiveKit reais é considerado aprovado até a execução em staging.

## Incremento validado — provisionamento de números

- API administrativa multi-tenant para buscar, comprar, listar, atribuir e liberar números.
- Adaptador Twilio conforme os contratos REST de inventário, compra e liberação.
- Dispatch rule inbound do LiveKit SIP, com compensação quando a criação ou persistência falha.
- Implementações determinísticas de desenvolvimento/teste, sem credenciais externas.
- Persistência PostgreSQL com RLS e histórico; migração `0006` permite recomprar números liberados mantendo unicidade apenas entre números ativos.
- Painel “Números” com busca por DDD, compra, atribuição a agente publicado e liberação.
- Secrets preparados no Terraform e no workflow de staging.
- `POST /v1/calls/outbound` com seleção do número atribuído ao agente, end-user, variáveis e metadata.
- Idempotência de 24 horas em Redis, incluindo reserva concorrente, replay e rejeição da mesma chave com payload diferente.
- Dispatch explícito do `agent-worker` ao criar a sala; o worker executa `CreateSIPParticipant` e persiste `queued → ringing → in_progress|failed`.
- Contratos OpenAPI e tipos TypeScript regenerados para o endpoint outbound.

## Evidências locais

- Terraform `fmt -check` e `validate`: aprovado.
- Ruff e mypy: aprovados.
- Suíte Python: 96 testes aprovados, cobertura global 82,15% (gate ≥ 80%).
- Testes JavaScript: 8 aprovados; lint, typecheck e builds aprovados.
- Testes de API/provedor: busca/compra/atribuição/liberação e outbound aprovados.
- Teste PostgreSQL de persistência e isolamento: aprovado.
- Teste Redis real de idempotência: aprovado.
- Testes do worker para sucesso e falha SIP outbound: aprovados.
- Playwright: 3 fluxos aprovados, incluindo compra → atribuição → liberação.
- Alembic local: `0006 (head)`.

## Itens ainda em implementação

- Trunks Twilio/LiveKit e validação real inbound/outbound.
- Pipeline de telefone além da discagem base, AMD/voicemail, DTMF, transferências cold/warm e SMS.
- Horário de funcionamento e mensagem fora do horário.
- Campanhas, janela, concorrência, retry, opt-out e do-not-call.
- Painel de campanhas, canais e `/live`; templates 5 e 6; métricas de rede/MOS.
- Ensaios de latência, barge-in, voicemail e carga de 50 salas.

## Pendências de provedores

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_SIP_DOMAIN`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `LIVEKIT_SIP_TRUNK_ID_INBOUND`
- `LIVEKIT_SIP_TRUNK_ID_OUTBOUND`

Quando as contas estiverem disponíveis, executar os critérios de aceite reais descritos em `docs/14-fases.md`; até lá, eles permanecem explicitamente pendentes.
