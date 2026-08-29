# Diagnóstico do fechamento: homologação local x produto

Registro dos problemas encontrados ao validar uma conversa de voz no ambiente
local. O Keyring foi excluído desta classificação.

## Itens do ambiente de teste local

Estes itens pertencem ao estado/configuração da homologação e não representam,
isoladamente, defeitos do SaaS em produção:

- O tenant de demonstração tinha o trial antigo e consumo acumulado. Em
  `APP_ENV=dev/test`, a expiração e a franquia de minutos foram flexibilizadas
  para permitir demonstrações sem cobrança.
- Havia chamadas órfãs antigas em `queued/in_progress`. Elas foram encerradas
  no banco local. A rotina de expiração automática agora encerra sessões
  abandonadas; em uma nova instalação, o banco deve começar limpo.
- O endereço LiveKit usado na homologação é o projeto cloud de demonstração.
  Ele precisa ser fornecido como variável de ambiente em cada serviço.

Esses ajustes não devem ser levados para produção como bypass de cobrança.
Produção deve manter trial, franquia, concorrência e suspensão normalmente.

## Erros estruturais do produto

Estes problemas poderiam ocorrer em qualquer instalação e foram corrigidos no
código/configuração:

1. **Contrato de runtime incompleto.** O endpoint interno não enviava `name` do
   agente e do tenant. Prompts com `{{ agent.name }}` causavam
   `jinja2.UndefinedError` e derrubavam o worker ao entrar na sala.
2. **Configuração divergente da API e do worker.** O worker tinha `LIVEKIT_URL`,
   mas a API não. A API devolvia `wss://example.invalid` ao navegador,
   impedindo a conexão WebRTC. O Compose agora injeta URL, API key e secret nos
   dois serviços.
3. **Leitura prematura de metadata LiveKit.** O worker tentava usar metadata da
   sala antes da conexão. O dispatch agora usa também a metadata do job,
   disponível na inicialização.
4. **Falha de compatibilidade no pipeline Anthropic.** A inicialização podia
   cair por incompatibilidade `httpx/httpx2` e interromper toda a conversa. Foi
   adicionado fallback para OpenAI.
5. **Inicialização ElevenLabs inconsistente.** O plugin não recebia
   explicitamente a variável usada pelo projeto. A chave agora é passada ao
   construtor do TTS.
6. **Diagnóstico insuficiente no painel.** Erros diferentes apareciam apenas
   como “Falha na conexão”. O widget agora exibe uma mensagem operacional
   específica e mantém o detalhe técnico nos logs.

## Correções de robustez já entregues

- Expiração automática: `queued/ringing` sem atividade por 5 minutos e
  `in_progress` sem atividade por 2 horas são marcadas como `failed`, com
  `end_reason=runtime_timeout`. O worker executa a rotina a cada 30 segundos e
  existe o endpoint operacional `/internal/calls/tick`.
- Validação de configuração: fora de `dev/test`, a API recusa URLs LiveKit de
  placeholder, chaves padrão, segredos fracos e URLs de aplicação inválidas no
  startup (`validate_runtime_settings`).

## Verificação atual (2026-08-29)

- `docker compose ps`: 7 serviços ativos (`db`, `redis`, `api`, `web`,
  `agent-worker`, `worker`, `mock`).
- API `http://localhost:8005/health`: `200 OK`; database, Redis, S3 e token
  LiveKit reportados como saudáveis.
- UI `http://localhost:3000`: `200 OK`.
- Testes locais previamente aprovados: 169 testes Python, cobertura backend
  mínima de 80%, lint e E2E do dashboard aprovados (ver
  `COMMERCIAL-READINESS.md`).

## Pendência que ainda exige prova externa

- Reexecutar um E2E completo com microfone real, STT, LLM, TTS, barge-in,
  gravação e encerramento da chamada. Esse teste é parte do gate de voz real de
  produção e não pode ser substituído por um teste HTTP ou mock.

Os demais gates comerciais (PSTN/Twilio, Stripe, AWS/observabilidade e
widget em domínio externo) estão listados em `COMMERCIAL-READINESS.md` e
continuam pendentes até que existam relatórios datados com evidência real.
