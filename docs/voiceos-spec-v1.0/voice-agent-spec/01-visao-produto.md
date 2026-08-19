# 01 — Visão do Produto

## Nome de trabalho
`VoiceOS` (substituir pelo nome comercial; usar `voiceos` como prefixo em código, buckets e recursos).

## O que é
Plataforma SaaS multi-tenant que permite criar, configurar e operar agentes de voz conversacionais que atendem por web, telefone e WhatsApp, consultam dados do cliente via tools e executam ações, com interrupção natural (barge-in) e troca de contexto no meio da conversa.

## Quem usa

| Persona | Papel | O que faz no produto |
|---|---|---|
| Agência (owner) | Você / sua empresa | Cria tenants, configura agentes, integra sistemas, acompanha uso e cobra |
| Tenant admin | Dono ou gestor do cliente final | Edita prompt, base de conhecimento, vozes, horários; vê chamadas e métricas; gerencia usuários do seu tenant |
| Tenant operator | Atendente/supervisor do cliente | Vê chamadas, ouve gravações, recebe transferências, marca qualidade |
| Tenant viewer | Financeiro/diretoria do cliente | Vê dashboards e faturas |
| Usuário final | Pessoa que liga ou fala com o agente | Não usa o painel |

## Casos de uso alvo (v1)

1. **Atendimento receptivo (inbound)**: cliente liga, agente identifica, responde dúvidas da base de conhecimento, consulta status (pedido, agendamento, fatura) via tool, transfere para humano quando necessário.
2. **Agendamento**: agente consulta disponibilidade, marca, remarca e cancela via tool (Google Calendar nativo ou webhook do cliente).
3. **Qualificação de lead (outbound e inbound)**: agente faz perguntas, registra respostas, cria lead no CRM via tool, agenda follow-up.
4. **Assistente no produto (web/app)**: widget de voz embutido no site ou app do cliente, autenticado por token, com acesso a dados do usuário logado.
5. **Nota de voz no WhatsApp**: usuário manda áudio, agente transcreve, responde em texto e áudio, com as mesmas tools.

## Requisitos funcionais (RF)

| ID | Requisito | Fase |
|---|---|---|
| RF-01 | Criar/editar/pausar/excluir agente por tenant | 1 |
| RF-02 | Configurar prompt do sistema com variáveis e templates | 1 |
| RF-03 | Escolher voz, idioma, velocidade, estilo por agente | 1 |
| RF-04 | Base de conhecimento por agente: upload PDF/DOCX/TXT/URL, chunking, embedding, RAG | 1 |
| RF-05 | Conversa por WebRTC com barge-in e latência alvo (`05-voice-pipeline.md`) | 1 |
| RF-06 | Sistema de tools: nativas (calendar, e-mail, SMS, transferência) e webhook do cliente | 1 |
| RF-07 | Histórico de conversas com transcrição, áudio, tools chamadas, custo, latências | 1 |
| RF-08 | Painel multi-tenant com RBAC | 1 |
| RF-09 | Número de telefone BR por agente, inbound via SIP | 2 |
| RF-10 | Outbound: chamada individual e campanha por lista com janela de horário | 2 |
| RF-11 | Transferência para humano (warm e cold) por telefone e web | 2 |
| RF-12 | Detecção de secretária eletrônica em outbound (AMD) | 2 |
| RF-13 | Billing: planos, medição de minutos, fatura, suspensão por inadimplência | 3 |
| RF-14 | API pública com API key por tenant | 3 |
| RF-15 | Avaliação automática de qualidade da conversa (LLM as judge) | 3 |
| RF-16 | WhatsApp: nota de voz e texto via Cloud API | 4 |
| RF-17 | Testes de conversa simulados (agente conversa com agente) no painel | 4 |
| RF-18 | Widget web embutível (`<script>`) e SDK JS | 5 |
| RF-19 | White-label do painel por tenant (logo, cor, domínio) | 5 |
| RF-20 | Exportação de dados e exclusão por LGPD | 3 |

## Requisitos não funcionais (RNF)

| ID | Requisito | Meta |
|---|---|---|
| RNF-01 | Latência voz-para-voz (fim da fala do usuário → primeiro áudio do agente), p50 | ≤ 900 ms web · ≤ 1.200 ms telefone |
| RNF-02 | Latência voz-para-voz, p95 | ≤ 1.800 ms |
| RNF-03 | Tempo de reação ao barge-in (usuário começa a falar → agente silencia) | ≤ 300 ms |
| RNF-04 | Disponibilidade da API e do pipeline | 99,5% mensal (v1) · 99,9% (v2) |
| RNF-05 | Conversas simultâneas por tenant | 50 (v1), sem limite arquitetural |
| RNF-06 | Isolamento de dados entre tenants | RLS no banco + escopo por `tenant_id` em toda query |
| RNF-07 | Dados em repouso e em trânsito | Criptografados (TLS 1.2+, S3 SSE-KMS, Postgres encrypted volume) |
| RNF-08 | Retenção de gravações | Configurável por tenant, padrão 90 dias |
| RNF-09 | Custo por minuto de conversa (infra + APIs), meta | ≤ USD 0,10/min telefone · ≤ USD 0,08/min web |
| RNF-10 | Tempo de deploy | ≤ 10 min, zero downtime |

## Fora de escopo (v1)
- Speech-to-speech nativo (modelos de áudio end-to-end). Arquitetura permite adicionar depois.
- Chamada de voz pelo WhatsApp (Calling API). Só nota de voz e texto.
- Vídeo.
- Marketplace de tools de terceiros.
- App mobile próprio (SDK JS cobre web e webview).

## Métricas de sucesso do produto
- Taxa de resolução sem humano ≥ 60% nos casos de uso 1 e 2
- Taxa de abandono na conversa ≤ 15%
- CSAT coletado ao final ≥ 4,2/5
- Latência p50 dentro do RNF-01 em 95% dos dias
