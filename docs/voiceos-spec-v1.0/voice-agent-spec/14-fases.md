# 14 — Fases de Execução

Ordem obrigatória. Cada fase termina com todos os critérios de aceite verificados. Estimativas para 1 engenheiro sênior com agente de código; ajustar conforme time.

---

## Fase 0 — Fundação (1 semana)
**Objetivo**: repositório, infra local, CI, esqueleto dos 4 serviços, banco com migrações, auth.

Entregáveis:
- Monorepo conforme `02`; Docker Compose sobe `db`, `redis`, `api`, `web`, `agent-worker`, `worker`, `mock` (servidor HTTP fake para tools).
- Alembic com todas as tabelas de `03` (podem nascer vazias de lógica); RLS habilitado; `make seed`.
- FastAPI com auth JWT, middleware de tenant (`SET LOCAL`), erros padrão, OpenAPI, `/health`.
- Next.js com Auth.js (magic link via Resend, Google), layout do painel, rota `/app/[t]` vazia, geração de tipos da OpenAPI.
- CI GitHub Actions (lint, mypy, pytest, vitest, build).
- Terraform inicial: VPC, RDS, ElastiCache, S3, ECR, ECS cluster, ALB, secrets (staging).
- OTel + Sentry ligados; logs JSON.

Aceite: `make dev` sobe tudo em < 3 min; login funciona; `GET /v1/me` retorna tenant; testes de isolamento RLS passam para `tenants/agents/calls`; deploy em staging por CI.

---

## Fase 1 — Agente de voz por WebRTC + painel essencial (3–4 semanas)
**Objetivo**: criar agente no painel, testar no navegador com barge-in, KB e tools; ver chamada com transcrição e áudio.

Entregáveis:
- `agent-worker` completo conforme `05` (VAD, STT Deepgram, LLM Claude com tools, TTS ElevenLabs, barge-in, filler, silêncio, duração máxima, RAG, fallbacks, métricas, custo).
- API: agents/versions/publish/rollback, sessions, calls (+live SSE), knowledge-bases/documents (ingestão: extração PDF/DOCX/HTML, chunking, embeddings OpenAI, pgvector), tools (nativas `end_call`, `set_variable`, `send_email`, `google_calendar_*` com OAuth; webhook completo com teste), internal endpoints, gravação via Egress → S3, pós-processamento (resumo/outcome com Haiku).
- Painel: onboarding, dashboard básico, editor do agente (abas Prompt, Voz, Conversa, Conhecimento, Tools, Avançado), widget de teste, lista e detalhe de chamadas com player e transcrição sincronizada, knowledge, tools, members, settings gerais e API keys.
- Templates de agente 1, 2 e 4 (`07`).
- Suíte de conversas em modo texto (≥ 25 casos) e modo áudio (≥ 10).

Aceite: RNF-01/02/03 medidos em staging (relatório com 50 conversas de teste); barge-in funcional em ≥ 95% dos casos da suíte; KB responde e não inventa nos casos de teste; tool webhook com `mock` funciona incluindo timeout e erro; publicar/rollback funcionam; E2E Playwright do fluxo "criar agente → publicar → testar → ver chamada" verde; isolamento multi-tenant testado; custo por minuto web medido ≤ RNF-09.

---

## Fase 2 — Telefone (3 semanas)
**Objetivo**: número BR inbound e outbound, transferência, campanhas.

Entregáveis:
- Terraform/scripts de trunk Twilio + LiveKit SIP; `phone-numbers` (buscar, comprar, atribuir, liberar, dispatch rules).
- Ajustes de pipeline para telefone (`05` tabela por canal), AMD por transcrição, voicemail message, DTMF tool, `transfer_call` cold e warm, `send_sms`.
- Horário de funcionamento e mensagem fora do horário.
- Outbound API + campanhas (`09`) com janela, concorrência, retry, opt-out, do-not-call.
- Painel: números, canais no agente, campanhas (criar, importar CSV, acompanhar), `/live` com assumir chamada (bridge para ramal do operador), templates 5 e 6.
- Métricas de rede/MOS.

Aceite: chamada real de celular para número comprado atende em ≤ 2 s após conectar; TTFB p50 ≤ 1.200 ms telefone; barge-in ≤ 300 ms com `min_interruption_words=2`; transferência warm e cold testadas com número real; campanha de 20 contatos executa respeitando janela e concorrência; voicemail detectado e mensagem deixada em ≥ 80% dos casos de teste; carga de 50 salas simultâneas conforme `13`.

---

## Fase 3 — Billing, API pública, qualidade, LGPD (2–3 semanas)
**Objetivo**: cobrar, abrir API, medir qualidade, cumprir LGPD.

Entregáveis:
- `10` completo: planos, Stripe sync, checkout, portal, medição, excedente, números como item, limites (402), trial, suspensão, avisos 80/100%.
- API keys secret, docs públicas (Redoc em `/docs`), webhooks de saída com assinatura e retries, `end-users` (com `lookup_end_user` tool), exports, exclusão LGPD, retenção e purga.
- QA por LLM (`call_qa`), avaliação manual no detalhe da chamada, analytics (`/v1/analytics/*`) e dashboard completo.
- Painel: billing, end-users, webhooks, exports, retenção nas settings; admin (`/admin`).
- Docs: `docs/dpa.md`, `docs/subprocessors.md`, `docs/incident-lgpd.md`, política de privacidade template.

Aceite: ciclo completo em Stripe test (trial → upgrade → uso → excedente → fatura → falha de pagamento → suspensão → reativação); usage bate com `calls` (teste de reconciliação); webhook de saída recebido por endpoint de teste com assinatura válida e retry após falha; exclusão de end-user remove/anonimiza tudo (teste automatizado); QA gera score em 100% das chamadas concluídas; dashboards de `12` provisionados; alertas disparam em teste de caos (derrubar Deepgram key → fallback + alerta).

---

## Fase 4 — WhatsApp e simulador (2–3 semanas)
**Objetivo**: mesmo agente no WhatsApp; testes de conversa pelo painel.

Entregáveis:
- Integração WhatsApp Cloud API (`09`): conexão do número, webhook, pipeline assíncrono, áudio in/out, `whatsapp_reply_mode`, handoff humano por texto no `/live`.
- Simulador no painel: usuário define "persona do cliente" e objetivo; plataforma roda N conversas agente-vs-agente (modo texto), mostra transcrições, tools chamadas, score QA; salva como casos da suíte (exporta YAML).
- Painel: integrações WhatsApp, chat de handoff, tela do simulador.

Aceite: mensagem de áudio no WhatsApp respondida com texto+áudio em ≤ 8 s p50; tools funcionam pelo WhatsApp; handoff humano funciona; simulador roda 20 conversas e gera relatório; suíte nightly inclui casos WhatsApp.

---

## Fase 5 — Widget embutível, SDK, white-label (2 semanas)
**Objetivo**: distribuir para sites dos clientes e personalizar marca.

Entregáveis:
- `packages/widget`: `voiceos.js` (≤ 60 KB gz), botão flutuante, temas, posição, textos, eventos; SDK `@voiceos/web` publicado no npm; docs com exemplos (HTML, React, Next).
- White-label: logo, cores, favicon, nome do produto, domínio custom (`CNAME` + certificado via ACM/Vercel), e-mails com marca do tenant.
- Painel: aba Canais com snippet, settings/branding.

Aceite: widget funciona em site estático de teste e em app React; origem não autorizada recebe 403; domínio custom em staging com TLS; Lighthouse do site host não cai mais de 5 pontos com o widget.

---

## Depois da Fase 5 (backlog priorizado, não especificado aqui)
Speech-to-speech como provider alternativo; chamada de voz WhatsApp; SIP direto de PABX corporativo; multi-idioma automático por detecção; marketplace de tools; app mobile SDK nativo; Kubernetes se ECS limitar.
