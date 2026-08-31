# Integrações MCP no VoiceOS

O VoiceOS aceita servidores MCP externos e privados como ferramentas de agente. A integração é deliberadamente bloqueada até que seja habilitada no ambiente e aprovada por ferramenta.

## Ativação do ambiente

Defina `MCP_ENABLED=true` no serviço API. Em produção, use HTTPS e informe `MCP_ALLOWED_HOSTS=api.exemplo.com,mcp.empresa.com` para restringir os destinos aceitos. A allowlist é opcional, mas recomendada. Para um servidor privado atrás de VPN/túnel, habilite também `MCP_ALLOW_PRIVATE_NETWORK=true`; esse acesso permanece bloqueado por padrão.

## Fluxo de configuração

1. Guarde o token do servidor em `POST /v1/secrets`; o valor nunca é retornado pela API.
2. Descubra as operações com `POST /v1/tools/mcp/discover`, usando `endpoint`, `transport` (`streamable_http` ou `sse`) e, se necessário, `auth` com `secret_id`.
3. Crie uma ferramenta com `type: "mcp"`, o schema da operação em `parameters_schema` e `mcp.operation` igual ao nome descoberto.
4. Revise o schema e só então marque `mcp.approved: true` e `mcp.enabled: true`.
5. Vincule a ferramenta à versão de rascunho do agente e publique essa versão.

Exemplo de configuração persistida:

```json
{
  "type": "mcp",
  "name": "consultar_pedido",
  "description": "Consulta um pedido no ERP.",
  "parameters_schema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
  "mcp": {
    "endpoint": "https://mcp.empresa.com/mcp",
    "transport": "streamable_http",
    "operation": "lookup_order",
    "auth": {"type": "bearer", "secret_id": "UUID_DO_SEGREDO"},
    "timeout_ms": 8000,
    "approved": true,
    "enabled": true
  }
}
```

## Proteções aplicadas

- Feature flag desativada por padrão.
- HTTPS e resolução para endereços públicos fora de desenvolvimento/teste.
- Allowlist de hosts para MCP quando configurada.
- Segredos cifrados pelo cofre existente; não entram em prompts, transcrições ou respostas.
- Descoberta não persiste nem expõe operação ao agente.
- Ferramentas MCP sem `approved` e `enabled` não entram no runtime e são recusadas pelo gateway.
- Todas as chamadas passam pelo mesmo registro de tool calls usado por webhooks e integrações nativas.
