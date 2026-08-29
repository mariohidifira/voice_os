# Plano de implementação — tomada universal de integrações

Status: plano aprovado para continuidade  
Escopo: transformar as integrações do VoiceOS em opções configuráveis, sem alterar o fluxo de voz já existente.

## 1. Objetivo

Permitir que um administrador escolha, por agente e por ferramenta, entre:

1. ferramenta nativa VoiceOS;
2. API REST ou webhook;
3. servidor MCP externo;
4. servidor MCP privado dentro da infraestrutura do cliente.

A LLM não deve receber acesso direto ao banco ou às credenciais. O agente solicita uma ferramenta; o gateway VoiceOS valida a política, executa o conector e devolve somente o resultado permitido.

## 2. Arquitetura-alvo

```text
voz / chat
   ↓
Agent Runtime
   ↓ tool intent
Tool Gateway VoiceOS
   ├─ NativeAdapter
   ├─ RestWebhookAdapter
   └─ McpAdapter (stdio, SSE ou Streamable HTTP)
   ↓ policy + secrets + audit
Sistema do cliente / serviço externo
```

O gateway é o ponto único de autorização, timeout, retry, redaction, rate limit, auditoria e contabilização.

## 3. Modelo de configuração

Adicionar ao registro de ferramenta:

```json
{
  "kind": "native | rest | webhook | mcp",
  "transport": "stdio | sse | streamable_http",
  "endpoint": "https://cliente.example/mcp",
  "server_name": "crm-cliente",
  "operation": "customers.search",
  "input_schema": {},
  "output_schema": {},
  "secret_ref": "secret://tenant/crm-token",
  "allowed_agents": [],
  "allowed_roles": ["agent"],
  "timeout_ms": 8000,
  "approval_required": false,
  "redaction_rules": []
}
```

O campo `kind` é a decisão de produto; o agente não precisa conhecer detalhes de transporte.

## 4. Fases de implementação

### Fase 0 — contrato e segurança

- Formalizar `ToolDefinition`, `ToolInvocation` e `ToolResult` versionados.
- Definir allowlist de hosts, ferramentas e operações.
- Implementar validação de schema de entrada e saída.
- Definir política de dados sensíveis, timeout, retry e limite de payload.
- Testes de negação: ferramenta não autorizada, tenant incorreto, segredo ausente e host fora da allowlist.

### Fase 1 — abstração do gateway

- Extrair o executor atual para uma interface `ToolAdapter`.
- Implementar `NativeAdapter` preservando as integrações existentes.
- Implementar `RestAdapter` e `WebhookAdapter` com autenticação por referência de segredo.
- Manter compatibilidade com o endpoint atual `execute_tool`.
- Registrar início, fim, latência, status, custo e erro sem registrar segredos.

### Fase 2 — MCP público/externo

- Adicionar `McpAdapter` com transporte Streamable HTTP; manter SSE como compatibilidade.
- Fazer descoberta explícita de ferramentas e exigir aprovação administrativa antes de publicar uma operação.
- Mapear schema MCP para o contrato interno do VoiceOS.
- Aplicar timeout, cancelamento, retry limitado e circuit breaker.
- Testar com um servidor MCP de demonstração controlado pelo projeto.

### Fase 3 — MCP privado do cliente

- Documentar execução do servidor MCP dentro da rede do cliente.
- Suportar conexão privada por HTTPS, túnel ou rede compartilhada; nunca expor banco diretamente ao worker.
- Permitir que o cliente mantenha credenciais e logs no próprio ambiente.
- Adicionar health check, rotação de segredo e revogação sem alterar o agente.

### Fase 4 — painel administrativo

- Criar seletor de tipo: Nativa, REST/Webhook, MCP externo ou MCP privado.
- Exibir somente os campos exigidos pelo tipo escolhido.
- Tela de descoberta MCP com lista de operações, schema, permissões e botão “aprovar”.
- Teste isolado da ferramenta com payload de exemplo e resposta mascarada.
- Mostrar claramente onde cada credencial fica armazenada.
- Exibir toggle de LLM externa separadamente das ferramentas: desligado significa modo local/determinístico.

### Fase 5 — runtime e experiência de voz

- O prompt recebe apenas nomes, descrição e schemas aprovados.
- O worker chama exclusivamente o gateway.
- Para operações longas, emitir filler configurável (“Só um momento…”) antes da execução.
- Para ações críticas, solicitar confirmação verbal e/ou aprovação humana.
- Persistir evidências da chamada, sem conteúdo sensível desnecessário.

### Fase 6 — produção e migração

- Migrar ferramentas atuais para `NativeAdapter` sem mudança funcional.
- Habilitar REST/Webhook por tenant.
- Liberar MCP por feature flag para tenants-piloto.
- Medir latência, falhas, custo e taxa de conclusão.
- Só depois habilitar MCP privado como capacidade comercial geral.

## 5. Critérios de aceite

- Um agente usa uma ferramenta nativa sem regressão.
- Um agente usa uma API REST com segredo fora do prompt.
- Um agente usa um webhook com assinatura e replay protegido.
- Um agente descobre e executa uma ferramenta MCP aprovada.
- Uma ferramenta MCP não aprovada nunca é exposta ao agente.
- Um servidor MCP fora da allowlist é bloqueado.
- O tenant A não consegue invocar ferramenta do tenant B.
- Logs mostram decisão, latência e resultado mascarado.
- Toggle de LLM externa desligado não inicia cliente Claude/OpenAI.
- Timeout ou indisponibilidade gera resposta cordial e evento auditável.

## 6. Entregáveis por etapa

- ADR de arquitetura e ameaça.
- Contratos JSON/TypeScript/Python versionados.
- Adaptadores e testes unitários.
- Servidor MCP fake para testes de integração.
- Migração de dados e feature flags.
- Painel com wizard de configuração.
- Runbook de instalação de MCP privado.
- Atualização das specs 04, 06, 07, 08, 11, 12 e 13.

## 7. Dependências e decisões pendentes

- Escolher biblioteca MCP oficial para Python/TypeScript.
- Definir se o transporte privado será exclusivamente HTTPS ou também stdio supervisionado.
- Definir política de aprovação para ações financeiras, exclusão e envio de mensagens.
- Definir retenção e localização dos logs por tenant.
- Definir quais modelos locais serão suportados na primeira versão.

## 8. Ordem recomendada para quem continuar

1. Ler este documento e `docs/voiceos-spec-v1.0/voice-agent-spec/06-tools-integracoes.md`.
2. Implementar a interface `ToolAdapter` sem alterar o comportamento atual.
3. Cobrir Native/REST/Webhook com testes de contrato.
4. Adicionar o servidor MCP fake e o `McpAdapter` atrás de feature flag.
5. Implementar o wizard administrativo e permissões.
6. Executar os critérios de aceite antes de habilitar qualquer MCP externo.

## Nota sobre a UI atual

O entry point já foi publicado no código e no Docker. Se a tela antiga aparecer, reconstruir o serviço `web` e recarregar com `Ctrl+F5`. A mensagem “Falha na conexão” do agente depende de LiveKit configurado e de uma sessão válida; isso é uma dependência de ambiente, não deve ser resolvido com credenciais dentro do front.
