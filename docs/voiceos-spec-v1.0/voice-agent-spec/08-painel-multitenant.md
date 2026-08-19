# 08 — Painel Multi-tenant (web)

Next.js 15 App Router. Rotas sob `/app/[tenantSlug]/...`. Platform admin tem `/admin`. Design: shadcn/ui, tema neutro, suporte a white-label na Fase 5 (`tenants.settings.branding`).

## RBAC

| Ação | owner | admin | operator | viewer | platform admin |
|---|---|---|---|---|---|
| Ver dashboards e chamadas | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ouvir gravações | ✓ | ✓ | ✓ | – | ✓ |
| Editar/publicar agentes | ✓ | ✓ | – | – | ✓ |
| Tools, KB, números | ✓ | ✓ | – | – | ✓ |
| Convidar membros | ✓ | ✓ | – | – | ✓ |
| Billing | ✓ | – | – | – | ✓ |
| API keys, webhooks | ✓ | ✓ | – | – | ✓ |
| Receber transferências | ✓ | ✓ | ✓ | – | – |
| Criar tenants, impersonar | – | – | – | – | ✓ |

Enforcement no backend (`required_role` por rota) e na UI (esconder ações).

## Mapa de telas

```
/login                          magic link + Google
/onboarding                     nome da empresa, timezone, primeiro agente (wizard 3 passos)
/app/[t]/                       Dashboard
/app/[t]/agents                 lista
/app/[t]/agents/new             escolher template
/app/[t]/agents/[id]            editor do agente (abas abaixo)
/app/[t]/calls                  lista + filtros
/app/[t]/calls/[id]             detalhe da chamada
/app/[t]/live                   chamadas em andamento (operator)
/app/[t]/knowledge              bases e documentos
/app/[t]/tools                  tools do tenant
/app/[t]/phone-numbers          números
/app/[t]/campaigns              (Fase 2)
/app/[t]/end-users              (Fase 3)
/app/[t]/settings/general       nome, timezone, gravação, retenção
/app/[t]/settings/members
/app/[t]/settings/integrations  Google, WhatsApp
/app/[t]/settings/api           API keys, webhooks
/app/[t]/settings/billing       (Fase 3)
/app/[t]/settings/branding      (Fase 5)
/admin/tenants, /admin/metrics
```

## Editor do agente (`/agents/[id]`)
Layout: barra superior com status (Draft alterado / Publicado v3), botões **Testar** (abre painel lateral com sessão WebRTC no draft, transcrição ao vivo, tools chamadas), **Publicar**, menu (versões, rollback, duplicar, arquivar).

Abas:
1. **Prompt**: editor com highlight de variáveis, painel de variáveis detectadas com valores default, contador de chars, botão "melhorar com IA" (chama LLM para reescrever seguindo `07`).
2. **Voz**: idioma, provider, lista de vozes com preview (botão play sintetiza frase padrão), velocidade, estabilidade. Saudação com preview.
3. **Conversa**: turn detection (presets: "rápido", "equilibrado", "paciente" que mapeiam para valores de `turn`), interrupções on/off, palavras mínimas, backchannels ignorados, silêncio, duração máxima, filler on/off + frases, frases de encerramento, horário de funcionamento + mensagem fora do horário, número de transferência.
4. **Conhecimento**: selecionar KB, top_k, botão "testar busca".
5. **Tools**: lista de tools do tenant com toggle; para nativas, campos extras (ex.: número de transferência); link "criar tool".
6. **Canais**: número(s) vinculado(s), snippet do widget web (Fase 5), status do WhatsApp (Fase 4).
7. **Avançado**: modelo LLM, temperature, max_tokens, STT keywords, JSON da versão (read-only), variáveis default.

Validações antes de publicar: prompt não vazio; voz escolhida; se `transfer_call` habilitado, número definido; tools webhook com teste ok; KB (se selecionada) com ≥ 1 documento `ready`.

## Detalhe da chamada (`/calls/[id]`)
- Cabeçalho: canal, números, duração, status, custo, latência p50/p95, score QA, tags, resultado.
- Player de áudio com waveform e transcrição sincronizada (clicar na fala pula o áudio).
- Timeline: turnos, barge-ins marcados, tools (expandir mostra args/result/latência), eventos.
- Resumo, variáveis coletadas, end_user (link).
- Ações: baixar áudio/transcrição, marcar qualidade manual (👍/👎 + nota), copiar id, reenviar webhook.

## Live (`/live`)
Cards de chamadas em andamento com transcrição via SSE, botão "assumir" (transferência para o operador: web → operador entra na room com microfone; telefone → liga para o ramal do operador e faz bridge). Notificação sonora em `transfer.requested`.

## Knowledge (`/knowledge`)
Upload drag-and-drop (PDF, DOCX, TXT, MD, até 25 MB), URL (crawler 1 nível, mesmo domínio, máx. 50 páginas), texto livre. Status por documento, contagem de chunks, reprocessar, excluir. Busca de teste.

## Tools (`/tools`)
Form: nome, descrição, tipo, parâmetros (editor de schema visual: nome/tipo/descrição/obrigatório + modo JSON), webhook (URL, método, headers, auth com seletor de secret, timeout, body template, response mapping com testador JSONPath), speak_before, async. Botão **Testar** com formulário gerado do schema.

## Widget de teste (usado no editor e na Fase 5 como embutível)
Componente React `<VoiceWidget sessionToken>`: botão microfone, indicador de estado (ouvindo / pensando / falando), transcrição opcional, botão encerrar. Usa `@livekit/components-react`.

## Estado e dados
- TanStack Query para API, SSE para live, Zustand só para estado de UI.
- Formulários com react-hook-form + zod (schemas em `packages/shared-ts` gerados da OpenAPI).
- i18n com `next-intl`, pt-BR default, en-US.

## Onboarding (novo tenant)
1. Nome da empresa, timezone.
2. Escolher template de agente, nome do agente, voz.
3. Testar no navegador (widget) → tela de sucesso com próximos passos: adicionar conhecimento, comprar número, criar tool.
