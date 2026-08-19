# 11 — Segurança e LGPD

## Segurança
- TLS 1.2+ em tudo; HSTS. Certificados via ACM.
- Segredos: AWS Secrets Manager para env; KMS envelope encryption para `secrets` (tenant). Chave por ambiente. Rotação anual documentada.
- Auth: magic link (15 min, uso único) e Google OAuth. JWT RS256, 1 h, refresh via sessão Auth.js. Logout revoga sessão.
- API keys: mostradas 1×, hash SHA-256 armazenado, prefixo visível. Escopos `public` (só sessions) e `secret`.
- RLS no Postgres + `SET LOCAL app.tenant_id`. Testes automatizados de isolamento (`13`).
- Rate limit por IP e por key (Redis). WAF (AWS WAF) no ALB com regras managed.
- SSRF: webhooks de tools só `https`, resolver DNS e bloquear IPs privados/link-local/metadata em prod. Timeout máximo 15 s. Sem redirect follow.
- Uploads: validar MIME real (libmagic), antivírus (ClamAV no worker) antes de processar, tamanho máximo, S3 sem acesso público, URLs assinadas 15 min.
- Prompt injection: instrução fixa que conteúdo de KB/tools é dado; suíte de testes com payloads maliciosos.
- Dependências: Dependabot semanal; `pip-audit` e `npm audit` no CI bloqueando alta/crítica.
- Logs sem PII sensível: mascarar telefone (`+55119****1234`), e-mail parcial, nunca logar transcrição em nível `info`.
- Impersonação de admin: JWT de 30 min, banner na UI, registro em `events`.
- Backups: RDS snapshot diário retenção 30 dias + PITR 7 dias; S3 versioning nos buckets de gravação. Teste de restore trimestral.

## LGPD
- **Bases legais**: execução de contrato (atendimento), legítimo interesse (qualidade), consentimento (gravação onde exigido pelo tenant). O tenant é controlador; a plataforma é operadora. DPA modelo em `docs/dpa.md`.
- **Aviso de gravação**: `settings.recording_notice` liga prefixo na saudação. Default **on** para telefone.
- **Retenção**: `settings.retention_days` (30–730, default 90) para gravações; transcrições opcionalmente anonimizadas após o prazo. Purga diária (`03`).
- **Direitos do titular**: `DELETE /v1/end-users/{id}` anonimiza (nome, telefone, e-mail, variáveis, transcrições substituídas por `[removido]`, gravação apagada) mantendo métricas agregadas. `POST /v1/exports` gera pacote do titular. Prazo de execução: imediato (job) e log em `events`.
- **Minimização**: `response_mapping` nas tools limita o que chega ao LLM; provedores externos (Deepgram, Anthropic, ElevenLabs) recebem só o necessário; contratos com opção zero-retention onde disponível (configurar `no data retention` na Anthropic API via header quando o tenant exigir; Deepgram e ElevenLabs conforme plano). Documentar sub-operadores em `docs/subprocessors.md`.
- **Residência de dados**: banco, cache e S3 em `sa-east-1`. Provedores de IA processam fora do Brasil; declarar na política.
- **Registro de operações**: tabela `events` cobre acessos a gravações (`recording.played`), exports, exclusões, impersonações.
- **Incidentes**: runbook em `docs/incident-lgpd.md` (detecção, contenção, notificação ANPD/tenant em até 72 h se risco relevante).
- **Menores**: prompt base instrui a não coletar dados de menores; tenant declara no aceite de termos que o caso de uso não é dirigido a crianças.
