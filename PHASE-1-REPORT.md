# Phase 1 Report

Status: **implementação local completa; aceite de mídia real em staging pendente de credenciais externas**.

## Entregáveis implementados

- Worker LiveKit Agents com Silero VAD, Deepgram STT, Claude, ElevenLabs TTS, fallbacks OpenAI/Cartesia, barge-in, backchannels, silêncio, duração máxima, RAG, tools, métricas, custo e encerramento drenado.
- API de agents, drafts, versions, publish/rollback, sessions, calls/SSE, KB/documents, tools, integrações nativas, endpoints internos, Egress/S3 e pós-processamento.
- Extração PDF, DOCX, HTML, URL e texto, chunking, embeddings OpenAI, pgvector e consulta isolada por tenant.
- Tools nativas `end_call`, `set_variable`, `send_email`, `google_calendar_check` e `google_calendar_book`; webhooks com schema, templates, SSRF guard, teste, timeout e erro recuperável.
- Painel essencial para agentes, templates, edição, tools vinculadas, teste WebRTC, chamadas, áudio/transcrição, conhecimento, membros, integrações, settings e API keys.
- Onboarding autenticado em duas etapas para criar tenant, owner, agente inicial por template e abrir imediatamente o teste de voz.
- Templates obrigatórios 1, 2 e 4: Recepcionista/FAQ, Agendamento e Suporte/Consulta de pedido.
- Playwright do fluxo login por magic link → criar agente → editar → publicar → testar → ver chamada.

## Evidências automatizadas locais

- `ruff check .`: aprovado.
- MyPy strict: aprovado em 33 arquivos.
- `pytest -q`: 69 testes aprovados.
- TypeScript, ESLint e build de produção Next.js: aprovados.
- Playwright essencial: 2 cenários aprovados contra PostgreSQL, mock HTTP e API em `localhost:8005`, cobrindo o fluxo administrativo e o onboarding completo.
- Isolamento PostgreSQL reforçado: toda sessão de tenant assume o papel `voiceos_app` (`NOSUPERUSER`/`NOBYPASSRLS`) antes de definir `app.tenant_id`; o E2E confirma que o novo tenant não enxerga agentes do tenant demo.
- RBAC de configuração: operator/viewer recebem 403 em KB, tools, secrets, integrações e membros; o painel carrega somente os recursos permitidos ao papel.
- Detalhe de chamada: player autenticado por URL S3 assinada e tenant-scoped, download, transcrição clicável sincronizada, custo, TTFB, reação ao barge-in, tools, eventos, resultado e variáveis coletadas.
- Editor avançado: modelo/temperatura/tokens, voz/velocidade/estabilidade, presets de turno, interrupções, backchannels, keywords STT, filler, transferência, variáveis e JSON read-only; persistência coberta no E2E.
- Editor organizado em seis abas acessíveis e funcionais (Prompt, Voz, Conversa, Conhecimento, Tools e Avançado), com navegação e persistência cobertas no E2E.
- Aba Prompt com limite/contador de 6.000 caracteres, detecção de variáveis Jinja e preview “Melhorar com IA”; o serviço Anthropic preserva variáveis, aplica timeout/retry e só persiste após revisão e salvamento explícito.
- Aba Voz com catálogo ElevenLabs, Voice ID manual como fallback, velocidade, estabilidade e preview da saudação em áudio; a chave do provedor permanece exclusivamente na API e ausência de configuração é exibida sem quebrar o painel.
- Controles completos de conversa para filler, frases de encerramento, prompt de silêncio, horário de funcionamento, mensagem fora do horário e transferência, preservados no `behavior` do rascunho.
- Aba Conhecimento configura KB, `top_k` e score mínimo e abre a busca de debug; aba Tools mantém toggles e atalho direto para criação de webhook.
- Ciclo administrativo do agente: pausar, reativar e excluir pelo painel.
- Conversas determinísticas: 40 casos texto + 10 casos áudio sintético, 100% aprovados.
- Barge-in determinístico: 4/4 casos aprovados; backchannels isolados também cobertos.
- KB: FAQ, ausência de resposta e injeção de prompt por documento cobertos.
- Tools: nativas, webhook OK, timeout, erro e injeção por resultado cobertos.
- Publish/rollback e isolamento multi-tenant cobertos na suíte API/PostgreSQL.
- Modelo de custo web representativo: USD 0,0458/min, abaixo do RNF-09 de USD 0,08/min.

Relatórios versionados:

- `reports/phase1-conversations-text.json`
- `reports/phase1-conversations-audio.json`
- `reports/phase1-cost-model.json`

Os tempos da suíte determinística são identificados como `simulated_turn_*` e **não** são usados como prova dos RNF de mídia.

## Critérios que exigem staging real

Os seguintes critérios não podem ser honestamente declarados concluídos no ambiente local com `LIVEKIT_URL=wss://example.invalid`:

- RNF-01: voz-para-voz p50 ≤ 900 ms no web.
- RNF-02: voz-para-voz p95 ≤ 1.800 ms.
- RNF-03: reação real do áudio ao barge-in ≤ 300 ms e sucesso ≥ 95%.
- Relatório de 50 conversas usando LiveKit, Deepgram, Anthropic e ElevenLabs reais.
- Gravação Egress real no S3 e reprodução do objeto remoto.
- Confirmação do custo efetivo por minuto contra usage/invoices dos provedores.
- Deploy e smoke test do ambiente AWS staging.

O workflow manual `phase1-staging-acceptance` busca os detalhes de 50 chamadas reais e falha se
qualquer gate de latência, barge-in, custo ou gravação não for atendido. O worker agora persiste
`barge_in_p50_ms` e `barge_in_p95_ms` a partir da métrica real de `detection_delay` do LiveKit.

As contas, nomes de secrets e ordem de configuração estão em `PROVIDER-SETUP-CHECKLIST.md`. Nenhum secret deve ser commitado.

## Comandos de reprodução

```powershell
python scripts/conversation_suite.py --mode text --report reports/phase1-conversations-text.json
python scripts/conversation_suite.py --mode audio --report reports/phase1-conversations-audio.json
pytest -q
npm run typecheck --workspace=@voiceos/dashboard
npm run lint --workspace=@voiceos/dashboard
npm run build --workspace=@voiceos/dashboard
npm run test:e2e --workspace=@voiceos/dashboard
```

## Decisão de gate

A implementação verificável sem fornecedores está aprovada. A Fase 1 permanece aberta até o workflow de staging produzir evidência dos RNF-01/02/03, Egress e custo real. Não avançar o gate formal para a Fase 2 antes dessas medições.
