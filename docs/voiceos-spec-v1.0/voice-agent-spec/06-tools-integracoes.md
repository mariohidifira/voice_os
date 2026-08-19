# 06 — Tools e Integrações

## Modelo
Uma tool é uma função exposta ao LLM. Duas categorias:
- **native**: implementadas na plataforma (transferir, encerrar, SMS, e-mail, calendário, DTMF, variáveis).
- **webhook**: o cliente cadastra URL, auth e schema; a plataforma chama.

O LLM vê todas como function calling padrão (`name`, `description`, `parameters` JSON Schema). Execução acontece na `api` (`POST /internal/tools/execute`) para manter segredos fora do `agent-worker`; nativas rápidas (`end_call`, `set_variable`, `dtmf`) executam no próprio worker.

## Schema de tool (tabela `tools`)

```json
{
  "name": "consultar_pedido",
  "description": "Consulta status de um pedido pelo número. Use quando o cliente perguntar sobre entrega, status ou rastreio.",
  "type": "webhook",
  "parameters_schema": {
    "type": "object",
    "properties": {
      "numero_pedido": { "type": "string", "description": "Número do pedido, apenas dígitos" }
    },
    "required": ["numero_pedido"]
  },
  "webhook": {
    "url": "https://api.cliente.com.br/pedidos/{{numero_pedido}}",
    "method": "GET",
    "headers": { "Accept": "application/json" },
    "auth": { "type": "bearer", "secret_id": "sec_..." },
    "timeout_ms": 8000,
    "body_template": null,
    "response_mapping": {
      "status": "$.data.status",
      "previsao": "$.data.previsao_entrega",
      "transportadora": "$.data.transportadora.nome"
    }
  },
  "speak_before": "Vou verificar seu pedido, um instante.",
  "async": false
}
```

Regras:
- `name` snake_case, ≤ 40 chars, único por tenant.
- `description` em pt-BR, diz **quando** usar. Máx. 300 chars.
- `url` e `body_template` aceitam `{{param}}` (params da chamada), `{{var.<nome>}}` (variáveis da sessão), `{{end_user.<campo>}}`, `{{call.id}}`, `{{call.from}}`.
- `auth.type`: `none` `bearer` `basic` `header` (`{name, secret_id}`) `hmac` (`{header, algorithm, secret_id}` assina o body).
- `response_mapping`: JSONPath → chave plana. Só o objeto mapeado vai ao LLM (limita tokens e evita vazar dados). Se `response_mapping` for null, vai o body inteiro truncado em 2.000 chars.
- `async: true`: dispara e responde `{"status":"accepted"}` ao LLM imediatamente (para ações sem retorno relevante, ex.: registrar log).
- Body de resposta > 20 KB → truncar e sinalizar.
- Resposta HTTP não-2xx → `{"error": "http_<status>", "message": <primeiros 200 chars>}` ao LLM.

## Contexto enviado a todo webhook
Header `X-VoiceOS-Call-Id`, `X-VoiceOS-Tenant-Id`, `X-VoiceOS-Agent-Id`, `X-VoiceOS-Signature` (HMAC do body com o secret do webhook_out do tenant, se configurado). Permite ao cliente correlacionar.

## Tools nativas

| name | parâmetros | comportamento |
|---|---|---|
| `end_call` | `{reason?: string, farewell?: string}` | Fala `farewell` (ou despedida padrão) e encerra. `end_reason=agent_hangup`. |
| `transfer_call` | `{destination?: string, reason: string, mode?: "warm"\|"cold"}` | `destination` default `behavior.transfer_number`. Telefone: SIP REFER (cold) ou cria participante SIP na room, agente resume o contexto ao humano em 1 frase e sai (warm). Web: notifica painel (`transfer.requested`) e mantém usuário em espera com mensagem; operador entra pela room. Registra `end_reason=transferred` na saída do agente. |
| `send_sms` | `{to?: string, message: string}` | Twilio SMS do número do agente. `to` default `call.from`. Só se `phone_numbers.capabilities.sms`. |
| `send_email` | `{to: string, subject: string, body: string}` | Resend, remetente do tenant (`settings.email_from`, verificado). |
| `google_calendar_check` | `{date: string, duration_min?: number}` | Retorna slots livres. Requer conexão OAuth Google do tenant (`08`). |
| `google_calendar_book` | `{start: datetime, duration_min: number, title: string, attendee_email?: string, notes?: string}` | Cria evento; retorna id e link. |
| `set_variable` | `{name: string, value: string}` | Grava em `session.variables`. Usado para coletar dados (nome, CPF, e-mail) declarados no prompt. |
| `dtmf` | `{digits: string}` | Envia tons (só telefone). Para navegar URA em outbound. |
| `lookup_end_user` | `{}` | Retorna `end_user` + últimas 3 chamadas resumidas do mesmo número/external_id (memória entre conversas). Habilitar por agente. |

Tools nativas são criadas por tenant no primeiro acesso (seed) e aparecem no painel como "prontas"; o usuário só liga/desliga por agente e ajusta `description`.

## Fluxo de execução

```
LLM emite tool_use {name, arguments}
 → worker valida arguments contra parameters_schema (jsonschema); erro → devolve ao LLM {"error":"invalid_arguments", "details":...}
 → se speak_before: enfileira TTS
 → nativa local: executa
 → senão POST /internal/tools/execute {tool_id, arguments, call_id, session_variables, end_user}
      api: renderiza template, resolve secret, chama com timeout, mapeia resposta, registra call_tool_calls
 → resultado (JSON) volta como tool_result
 → LLM continua
```
Paralelismo: se o LLM emitir múltiplos `tool_use` no mesmo turno, executar em paralelo (asyncio.gather).

## Teste de tool no painel
`POST /v1/tools/{id}/test` mostra: request renderizado, status, latência, body bruto, body mapeado, e o que o LLM veria. Obrigatório passar 1× antes de habilitar tool webhook em agente publicado (flag `tools.last_test_ok_at`).

## Integrações OAuth do tenant (para tools nativas)
Tabela `integrations`: `{tenant_id, provider ('google'), scopes, refresh_token (secret_id), account_email, status}`. Fluxo OAuth padrão em `/v1/integrations/google/connect` → callback → grava. Renovação de token automática no `worker`.

## Boas práticas embutidas (validação no painel)
- Aviso se `description` não contém "quando" ou "use quando".
- Aviso se um agente tem > 12 tools habilitadas (degrada precisão do LLM).
- Bloqueio se webhook aponta para IP privado/localhost em prod (SSRF). Allowlist de esquemas `https` apenas em prod.
