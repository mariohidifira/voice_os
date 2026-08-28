# Especificação Técnica — Plataforma de Agentes de Voz Multi-tenant

Versão 1.0 · Documento-mestre para execução por agente de código (Claude Code) ou time de engenharia.

## Como usar este pacote

1. Leia este arquivo inteiro antes de qualquer outro.
2. Execute as fases em ordem (`14-fases.md`). Não pule fase. Cada fase tem critérios de aceite verificáveis; só avance quando todos passarem.
3. Cada arquivo é a fonte de verdade do seu domínio. Se houver conflito entre arquivos, a ordem de precedência é: `14-fases.md` > `02-arquitetura.md` > arquivo específico do domínio.
4. Toda decisão já foi tomada. Não pergunte "qual banco usar" ou "qual framework". Está definido. Se algo não estiver definido, use a regra em "Regras para o agente executor" abaixo.
5. Nomes de tabelas, endpoints, variáveis de ambiente e eventos são contratos. Use exatamente como escritos.

## Decisões fechadas (não reabrir)

| Tema | Decisão | Motivo |
|---|---|---|
| Base técnica | Stack própria sobre LiveKit (Agents SDK Python + LiveKit Cloud para SFU/SIP) | Controle total do pipeline, margem, portabilidade de fornecedores de STT/LLM/TTS |
| Linguagem backend | Python 3.12 (FastAPI + LiveKit Agents) | Um único runtime para API e agente de voz; SDK de voz mais maduro em Python |
| Frontend painel | Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui | Padrão de mercado, SSR, componentes prontos |
| Banco | PostgreSQL 16 (com `pgvector` para RAG) | Um banco só para dados relacionais e vetores; menos infra |
| Cache/filas | Redis 7 | Sessões, rate limit, filas leves, pub/sub de eventos ao vivo |
| Object storage | S3 (AWS) | Gravações, transcrições, documentos da base de conhecimento |
| Região | AWS `sa-east-1` (São Paulo) | Latência para o Brasil e LGPD |
| STT | Deepgram Nova-3 (streaming, pt-BR) · fallback: OpenAI Whisper realtime | Melhor custo/latência para pt-BR em streaming |
| LLM | Anthropic Claude Sonnet (última versão estável) · fallback: OpenAI GPT-4.1 | Qualidade de tool use e instrução; latência aceitável |
| TTS | ElevenLabs Flash v2.5 (pt-BR) · fallback: Cartesia Sonic | Naturalidade em pt-BR e streaming |
| VAD / turn detection | Silero VAD + LiveKit turn detector | Padrão do LiveKit Agents, testado em produção |
| Canais | Fase 1: WebRTC (web/app) · Fase 2: telefone PSTN via LiveKit SIP + Twilio · Fase 4: WhatsApp (nota de voz + texto) | Ordem por complexidade e por retorno |
| Telefonia | Twilio Elastic SIP Trunking (números BR) | Cobertura BR, documentação, integração oficial com LiveKit SIP |
| Painel | Multi-tenant com RBAC: agência opera todos os tenants; cliente final opera o próprio | Requisito de produto |
| Billing | Stripe (cartão + Pix) · plano mensal + minutos excedentes | Cobre BR e exterior, webhooks maduros |
| Idiomas do agente | pt-BR primário; en-US e es-ES habilitáveis por agente | Mercado inicial BR |
| Auth | Auth.js (NextAuth) com e-mail magic link + Google · JWT para API | Simples, sem senha, sem custo |
| Infra | Docker Compose para dev · AWS ECS Fargate para produção · Terraform | Reprodutível, sem Kubernetes no início |
| Observabilidade | OpenTelemetry → Grafana Cloud (logs, métricas, traces) · Sentry para erros | Padrão aberto, custo baixo |

## Regras para o agente executor

- Sempre TypeScript estrito no frontend e type hints + `mypy --strict` no backend.
- Testes obrigatórios: cobertura mínima de 80% no backend, testes E2E (Playwright) nos fluxos críticos do painel.
- Nenhum segredo em código. Tudo via variáveis de ambiente listadas em `02-arquitetura.md`.
- Toda tabela tem `id UUID`, `tenant_id`, `created_at`, `updated_at`. Row Level Security por `tenant_id` no Postgres.
- Toda chamada externa (STT, LLM, TTS, Twilio, Stripe) tem timeout, retry com backoff e circuit breaker.
- Todo evento de negócio é registrado na tabela `events` (`03-modelo-dados.md`).
- Se uma decisão não estiver neste pacote, escolha a opção mais simples que atenda o critério de aceite da fase, documente em `DECISIONS.md` na raiz do repositório e siga.
- Commits pequenos, mensagens em inglês no formato Conventional Commits.
- Ao terminar cada fase, gere `PHASE-N-REPORT.md` com: o que foi feito, como testar, o que ficou fora.

## Índice

| Arquivo | Conteúdo |
|---|---|
| `01-visao-produto.md` | O que é o produto, personas, casos de uso, requisitos funcionais e não funcionais |
| `02-arquitetura.md` | Componentes, fluxo de dados, infra, variáveis de ambiente, repositório |
| `03-modelo-dados.md` | Schema Postgres completo, RLS, índices, migrações |
| `04-api-contracts.md` | REST API do painel e da plataforma, autenticação, erros, webhooks |
| `05-voice-pipeline.md` | Pipeline de voz: VAD, STT, LLM, TTS, barge-in, latência, fallbacks |
| `06-tools-integracoes.md` | Sistema de tools: schema, execução, tools nativas, tools de webhook do cliente |
| `07-prompts.md` | Estrutura de prompt do agente, prompts padrão, templates, variáveis |
| `08-painel-multitenant.md` | Telas, RBAC, fluxos do painel, componentes |
| `09-canais.md` | WebRTC, PSTN/SIP, WhatsApp: setup, fluxos, tratamento de erros |
| `10-billing.md` | Planos, medição de minutos, Stripe, limites, suspensão |
| `11-seguranca-lgpd.md` | Segurança, LGPD, retenção, criptografia, consentimento de gravação |
| `12-observabilidade.md` | Logs, métricas, traces, alertas, dashboards |
| `13-testes-aceite.md` | Estratégia de testes, suíte de conversas, testes de carga, critérios |
| `14-fases.md` | Roadmap em 5 fases, entregáveis, critérios de aceite, ordem de execução |
| `15-glossario.md` | Termos e siglas |
| `docker-homologacao.md` | Backup, restauração e reprodução do ambiente Docker de homologação |
