# Diagnóstico do fechamento: homologação local x produto

Registro dos problemas encontrados ao validar uma conversa de voz no ambiente local. O Keyring foi excluído desta classificação.

## Itens do ambiente de teste local

Estes itens pertencem ao estado/configuração da homologação e não representam, isoladamente, defeitos do SaaS em produção:

- O tenant de demonstração tinha o trial antigo e consumo acumulado. Em `APP_ENV=dev/test`, a expiração e a franquia de minutos foram flexibilizadas para permitir demonstrações sem cobrança.
- Havia chamadas órfãs antigas em `queued/in_progress`. Elas foram encerradas no banco local. Em uma nova instalação, o banco deve começar limpo ou executar a rotina de expiração de sessões abandonadas.
- O endereço LiveKit usado na homologação é o projeto cloud de demonstração. Ele precisa ser fornecido como variável de ambiente em cada serviço.

Esses ajustes não devem ser levados para produção como bypass de cobrança. Produção deve manter trial, franquia, concorrência e suspensão normalmente.

## Erros estruturais do produto

Estes problemas poderiam ocorrer em qualquer instalação e foram corrigidos no código/configuração:

1. **Contrato de runtime incompleto.** O endpoint interno não enviava `name` do agente e do tenant. Prompts com `{{ agent.name }}` causavam `jinja2.UndefinedError` e derrubavam o worker ao entrar na sala.
2. **Configuração divergente da API e do worker.** O worker tinha `LIVEKIT_URL`, mas a API não. A API devolvia `wss://example.invalid` ao navegador, impedindo a conexão WebRTC. O Compose agora injeta URL, API key e secret nos dois serviços.
3. **Leitura prematura de metadata LiveKit.** O worker tentava usar metadata da sala antes da conexão. O dispatch agora usa também a metadata do job, disponível na inicialização.
4. **Falha de compatibilidade no pipeline Anthropic.** A inicialização podia cair por incompatibilidade `httpx/httpx2` e interromper toda a conversa. Foi adicionado fallback para OpenAI.
5. **Inicialização ElevenLabs inconsistente.** O plugin não recebia explicitamente a variável usada pelo projeto. A chave agora é passada ao construtor do TTS.
6. **Diagnóstico insuficiente no painel.** Vários erros diferentes apareciam apenas como “Falha na conexão”. A causa real precisa continuar sendo registrada nos logs e, idealmente, apresentada ao operador (API, WebSocket, microfone ou worker).

## Verificação realizada

- API criou sessão de teste com `201 Created`.
- Worker recebeu job LiveKit e registrou-se na região Brazil.
- Endpoint ElevenLabs `/v1/voices` respondeu `200 OK`.
- Suíte local: 151 testes aprovados antes dos últimos ajustes; testes da API: 28 aprovados.

## Pendências recomendadas antes de produção

- Adicionar expiração automática de chamadas `queued/ringing/in_progress` sem atividade.
- Exibir a mensagem de erro específica no widget, mantendo detalhes técnicos apenas nos logs.
- Validar todas as variáveis obrigatórias no startup da API e do worker, recusando `*.invalid` fora de `dev/test`.
- Reexecutar um teste E2E completo com microfone, STT, LLM, TTS e encerramento da chamada.
