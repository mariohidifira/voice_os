# VoiceOS — Checklist de provedores e credenciais

Objetivo: reunir tudo o que precisa ser contratado, criado e configurado para liberar o staging e as fases seguintes do VoiceOS.

> **Segurança:** não escreva valores reais neste arquivo e não envie secrets por chat, issue ou commit. Cadastre-os diretamente em **GitHub → `mariohidifira/voice_os` → Settings → Environments → `staging` → Environment secrets**.

## 1. Prioridade imediata — concluir a Fase 0

### 1.1 AWS e GitHub OIDC

- [ ] Conta AWS ativa e com billing habilitado.
- [ ] Região de operação: `sa-east-1` (São Paulo).
- [ ] Provedor OIDC do GitHub cadastrado no IAM:
  - URL: `https://token.actions.githubusercontent.com`
  - Audience: `sts.amazonaws.com`
- [ ] IAM Role criada para o GitHub Actions.
- [ ] Trust policy limitada ao repositório `mariohidifira/voice_os` e ao environment `staging`.
- [ ] ARN da role cadastrado no GitHub.
- [ ] Sufixo globalmente único para buckets definido.

Secrets obrigatórios:

| Nome no GitHub | Conteúdo | Exemplo não secreto |
|---|---|---|
| `AWS_STAGING_ROLE_ARN` | ARN da IAM Role assumida pelo GitHub OIDC | `arn:aws:iam::123456789012:role/voiceos-github-staging` |
| `AWS_ACCOUNT_SUFFIX` | Sufixo único para buckets S3 | `voiceos-mario-stg` |

Trust policy de referência para a IAM Role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:mariohidifira/voice_os:environment:staging"
        }
      }
    }
  ]
}
```

O Terraform cria automaticamente:

- VPC, subnets públicas/privadas, Internet Gateway e NAT Gateway;
- ECS Fargate e ECR;
- RDS PostgreSQL 16 com pgvector;
- ElastiCache Redis 7;
- buckets S3 para gravações, documentos e exports;
- KMS, Secrets Manager, ALB e CloudWatch Logs.

### 1.2 Segredos internos

Gerar dois valores aleatórios diferentes, com pelo menos 32 bytes:

| Nome no GitHub | Finalidade |
|---|---|
| `AUTH_SECRET` | Assinatura e criptografia Auth.js/JWT |
| `INTERNAL_API_TOKEN` | Autenticação entre API e workers |

Exemplo de geração local:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

- [ ] `AUTH_SECRET` gerado e cadastrado.
- [ ] `INTERNAL_API_TOKEN` gerado separadamente e cadastrado.

### 1.3 Resend — magic link

Serviço: entrega dos e-mails de autenticação sem senha.

- [ ] Conta/projeto criado no Resend.
- [ ] Domínio de envio validado por DNS.
- [ ] Remetente definido, por exemplo `VoiceOS <login@seudominio.com>`.
- [ ] API key restrita ao envio criada.
- [ ] Secret cadastrado no GitHub.

| Nome | Onde usar |
|---|---|
| `RESEND_API_KEY` | GitHub environment secret |
| `AUTH_EMAIL_FROM` | Configuração do ambiente, com remetente validado |

### 1.4 LiveKit Cloud — WebRTC e voz

Serviço: salas WebRTC, SFU, Agents e Egress; posteriormente SIP.

- [ ] Projeto LiveKit Cloud criado em região adequada para usuários brasileiros.
- [ ] URL WebSocket copiada (`wss://...`).
- [ ] API key e API secret criados.
- [ ] Egress habilitado para gravações quando disponível.

| Secret | Conteúdo |
|---|---|
| `LIVEKIT_URL` | URL WebSocket do projeto |
| `LIVEKIT_API_KEY` | API key |
| `LIVEKIT_API_SECRET` | API secret |

### 1.5 Deepgram — STT principal

Serviço: transcrição streaming com Nova-3 em pt-BR.

- [ ] Projeto criado.
- [ ] Billing/créditos habilitados.
- [ ] API key criada e restrita ao projeto.
- [ ] `DEEPGRAM_API_KEY` cadastrado no GitHub.

### 1.6 Anthropic — LLM principal

Serviço: Claude Sonnet para diálogo e uso de tools.

- [ ] Workspace/projeto criado.
- [ ] Billing e limite de uso configurados.
- [ ] API key criada.
- [ ] `ANTHROPIC_API_KEY` cadastrado no GitHub.

### 1.7 OpenAI — fallback e embeddings

Serviços: fallback de LLM/STT e embeddings do RAG.

- [ ] Projeto separado para o VoiceOS.
- [ ] Billing e limites configurados.
- [ ] API key de projeto criada.
- [ ] `OPENAI_API_KEY` cadastrado no GitHub.

### 1.8 ElevenLabs — TTS principal

Serviço: síntese de voz Flash v2.5 em pt-BR.

- [ ] Conta/workspace criado.
- [ ] Plano com uso de API habilitado.
- [ ] Voz padrão selecionada ou criada.
- [ ] API key criada.
- [ ] `ELEVENLABS_API_KEY` cadastrado no GitHub.

## 2. GitHub environment `staging`

O environment já existe. Para liberar o workflow atual, todos os itens abaixo precisam estar preenchidos:

```text
AWS_STAGING_ROLE_ARN
AWS_ACCOUNT_SUFFIX
AUTH_SECRET
INTERNAL_API_TOKEN
RESEND_API_KEY
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
DEEPGRAM_API_KEY
ANTHROPIC_API_KEY
OPENAI_API_KEY
ELEVENLABS_API_KEY
```

Após o primeiro deploy e o seed de aceite, cadastrar também os valores operacionais usados pelo
workflow `phase1-staging-acceptance`:

| Nome | Conteúdo |
|---|---|
| `STAGING_API_URL` | URL pública do ALB/API, com `https://` |
| `STAGING_ACCEPTANCE_TOKEN` | JWT temporário do usuário de aceite; renovar antes de cada execução |
| `STAGING_TENANT_ID` | UUID do tenant usado exclusivamente nos testes de aceite |

O token não substitui `AUTH_SECRET` e não deve ser reutilizado em produção.

Checklist:

- [ ] Os 12 secrets acima existem no environment `staging`.
- [ ] Nenhum valor foi cadastrado como repository variable por engano.
- [ ] A IAM Role aceita apenas o repositório e environment esperados.
- [ ] O workflow `deploy-staging` foi executado manualmente.
- [ ] Terraform concluiu sem erro.
- [ ] Imagens foram publicadas no ECR.
- [ ] Migrações Alembic concluíram com exit code `0`.
- [ ] Serviços ECS ficaram estáveis.
- [ ] Smoke de `/health` e `/` passou.

## 3. Autenticação opcional — Google OAuth

Provedor: Google Cloud / Google Identity.

- [ ] Projeto Google Cloud criado.
- [ ] OAuth consent screen configurada.
- [ ] OAuth Client do tipo Web criado.
- [ ] Origens autorizadas configuradas.
- [ ] Callback Auth.js configurado: `https://<DOMINIO>/api/auth/callback/google`.

| Nome | Conteúdo |
|---|---|
| `GOOGLE_CLIENT_ID` | Client ID OAuth |
| `GOOGLE_CLIENT_SECRET` | Client secret OAuth |

Google é opcional para a Fase 0; o magic link via Resend é o caminho obrigatório.

## 4. Voz — complementos da Fase 1

### Cartesia — fallback de TTS

- [ ] Conta/projeto criado.
- [ ] API key criada.
- [ ] `CARTESIA_API_KEY` cadastrado.

É opcional no início, mas necessário para validar o fallback TTS especificado.

### AWS S3/KMS

Gerenciados pelo Terraform:

```text
AWS_REGION
KMS_KEY_ID
S3_BUCKET_RECORDINGS
S3_BUCKET_DOCUMENTS
S3_BUCKET_EXPORTS
```

Não criar valores manualmente antes do Terraform; o workflow injeta os nomes resultantes.

## 5. Telefonia — Fase 2

### Twilio

Serviços: números brasileiros, Elastic SIP Trunking, chamadas inbound/outbound e SMS.

- [ ] Conta empresarial criada e verificada.
- [ ] Billing habilitado.
- [ ] Número brasileiro comprado.
- [ ] Elastic SIP Trunk criado.
- [ ] Origination e termination configurados com LiveKit SIP.
- [ ] Credenciais SIP configuradas.

| Secret/configuração | Conteúdo |
|---|---|
| `TWILIO_ACCOUNT_SID` | SID da conta |
| `TWILIO_AUTH_TOKEN` | Token da conta ou subaccount |
| `TWILIO_SIP_DOMAIN` | Domínio de termination SIP |
| `TWILIO_MESSAGING_SERVICE_SID` | Messaging Service para envio de SMS |
| `LIVEKIT_SIP_TRUNK_ID_INBOUND` | ID do inbound trunk no LiveKit |
| `LIVEKIT_SIP_TRUNK_ID_OUTBOUND` | ID do outbound trunk no LiveKit |

Recomendação: usar uma subaccount Twilio exclusiva para staging.

## 6. Billing — Fase 3

### Stripe

Serviços: assinatura, cartão, Pix, excedentes, invoices e portal do cliente.

- [ ] Conta Stripe criada e verificada.
- [ ] Modo de testes selecionado.
- [ ] Produtos e prices dos planos criados.
- [ ] Pix habilitado quando elegível.
- [ ] Endpoint webhook configurado em `https://<DOMINIO>/v1/webhooks/stripe`.

| Secret | Conteúdo |
|---|---|
| `STRIPE_SECRET_KEY` | Secret key do modo test |
| `STRIPE_WEBHOOK_SECRET` | Signing secret do endpoint webhook |

Nunca usar uma chave `live` no staging.

## 7. WhatsApp — Fase 4

### Meta WhatsApp Cloud API

- [ ] Meta Business verificado.
- [ ] Aplicativo Meta criado.
- [ ] Produto WhatsApp adicionado.
- [ ] Número de telefone conectado.
- [ ] Webhook e verify token configurados.
- [ ] Token permanente criado via System User.

Nomes já previstos no contrato:

```text
WHATSAPP_APP_SECRET
WHATSAPP_VERIFY_TOKEN
```

Nomes que deverão ser formalizados na implementação da Fase 4:

```text
WHATSAPP_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_BUSINESS_ACCOUNT_ID
```

## 8. Observabilidade

### Grafana Cloud

Serviços: ingestão OTLP de métricas, logs e traces.

- [ ] Stack Grafana Cloud criada.
- [ ] Endpoint OTLP copiado.
- [ ] Token/headers OTLP criados com permissões mínimas.

```text
OTEL_EXPORTER_OTLP_ENDPOINT
OTEL_EXPORTER_OTLP_HEADERS
```

### Sentry

Serviço: captura e agrupamento de erros.

- [ ] Organização/projeto criado.
- [ ] DSN do projeto copiado.
- [ ] Alertas básicos configurados.

```text
SENTRY_DSN
```

## 9. Variáveis internas e não-provedores

Estas configurações pertencem ao VoiceOS, não a fornecedores externos:

```text
APP_ENV
APP_BASE_URL
AUTH_URL
AUTH_TRUST_HOST
API_BASE_URL
LOG_LEVEL
DATABASE_URL
REDIS_URL
JWT_ISSUER
JWT_AUDIENCE
AUTH_EMAIL_FROM
INTERNAL_API_TOKEN
AGENT_WORKER_MAX_ROOMS
```

## 10. Lote real de aceite da Fase 1

Depois do deploy e antes de executar `phase1-staging-acceptance`, defina um identificador único,
por exemplo `phase1-2026-08-22-01`. Todas as 50 sessões devem enviar:

```json
{
  "metadata": {
    "acceptance_run_id": "phase1-2026-08-22-01",
    "acceptance_barge_in": false
  }
}
```

Marque `acceptance_barge_in: true` em pelo menos 20 chamadas nas quais o participante realmente
interromper o agente. O lote somente é válido quando:

- [ ] 50 chamadas WebRTC reais do mesmo `acceptance_run_id` terminaram com status `completed`.
- [ ] Cada chamada tem pelo menos uma amostra real de TTFB produzida pelo LiveKit Agents.
- [ ] Pelo menos 20 chamadas exercitaram barge-in; sucesso mínimo de 95% e reação p95 até 300 ms.
- [ ] Todas registraram uso de STT, LLM e TTS, moeda USD, duração e custo positivo.
- [ ] Todas possuem gravação Egress com status `ready` e chave S3.
- [ ] Deepgram, Anthropic e ElevenLabs reais foram usados; nenhum mock/fallback local participa do lote.

Execute o workflow manual `phase1-staging-acceptance` e informe o mesmo valor no input `run_id`.
O artefato `phase1-staging-acceptance` conterá o relatório e o job falhará se qualquer evidência
estiver ausente ou fora dos RNF-01/02/03/09.

## 11. Ordem prática de execução

1. [ ] AWS + GitHub OIDC.
2. [ ] Gerar `AUTH_SECRET` e `INTERNAL_API_TOKEN`.
3. [ ] Criar LiveKit Cloud.
4. [ ] Criar Deepgram.
5. [ ] Criar Anthropic.
6. [ ] Criar OpenAI.
7. [ ] Criar ElevenLabs.
8. [ ] Configurar Resend e domínio de envio.
9. [ ] Cadastrar os 12 secrets no GitHub `staging`.
10. [ ] Executar `deploy-staging` manualmente.
11. [ ] Configurar Google OAuth, se desejado.
12. [ ] Configurar Grafana Cloud e Sentry.
13. [ ] Contratar/configurar Twilio na Fase 2.
14. [ ] Configurar Stripe na Fase 3.
15. [ ] Configurar Meta WhatsApp na Fase 4.

## 12. Registro de conclusão

| Grupo | Responsável | Data | Status/observação |
|---|---|---|---|
| AWS/OIDC |  |  |  |
| Secrets internos |  |  |  |
| Resend |  |  |  |
| LiveKit |  |  |  |
| Deepgram |  |  |  |
| Anthropic |  |  |  |
| OpenAI |  |  |  |
| ElevenLabs |  |  |  |
| Google OAuth |  |  |  |
| Grafana/Sentry |  |  |  |
| Twilio |  |  |  |
| Stripe |  |  |  |
| Meta WhatsApp |  |  |  |
