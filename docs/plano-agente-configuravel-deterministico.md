# Plano: agente configurável, determinístico e híbrido

## Objetivo

Preparar o VoiceOS para operar com processos definidos por configuração, sem exigir alteração de código para cada cliente ou cenário.

O agente deve poder trabalhar em três modos:

- `deterministic`: regras, etapas e respostas configuradas;
- `hybrid`: regras primeiro, com LLM somente para exceções;
- `llm`: comportamento conversacional atual.

O modo deve ser escolhido por versão do agente e publicado pelo administrador.

## Motivação

Em uma operação normal de atendimento, muitas interações são previsíveis: confirmação, coleta de dados, agendamento, cancelamento, transferência e encerramento. Consultar uma LLM em todos os turnos aumenta custo, latência e variação de idioma, tom e resposta.

A LLM deve ser uma capacidade opcional, não uma dependência estrutural de todos os processos.

## O que permanece igual

- LiveKit e a sessão de áudio;
- autenticação e emissão de tokens;
- STT e TTS configurados no agente;
- ferramentas de telefonia, transferência, DTMF e encerramento;
- registro de chamadas, turnos, eventos e métricas;
- modo `llm` existente, preservado para compatibilidade.

## Arquitetura proposta

```text
áudio -> STT -> estado do processo -> intenção
                         |
             +-----------+-----------+
             |                       |
       regra/transição          exceção
             |                       |
      resposta configurada     LLM opcional
             |                       |
             +-----------+-----------+
                         |
                        TTS
```

O estado do processo é a fonte de verdade. A LLM não pode pular etapas, executar uma ação sem confirmação ou substituir uma regra publicada.

## Modelo mínimo de configuração

Adicionar à versão do agente uma configuração semelhante a:

```json
{
  "execution_mode": "hybrid",
  "initial_state": "greeting",
  "states": [
    {
      "id": "greeting",
      "prompt": "Olá, posso confirmar seu agendamento?",
      "transitions": [
        {"intent": "yes", "next": "collect_name"},
        {"intent": "no", "next": "end"}
      ]
    }
  ],
  "intents": [
    {"id": "yes", "examples": ["sim", "pode", "confirmo"]}
  ],
  "llm_policy": {
    "enabled": true,
    "on_unknown_intent": true,
    "on_rag_request": true
  }
}
```

O formato definitivo deve ser validado por schema e versionado junto com `agent_versions`.

## Etapas de implementação

### 1. Contrato e persistência

- definir `execution_mode`, estados, intenções, transições e política de LLM;
- adicionar validação Pydantic e limites de tamanho;
- persistir em `agent_versions` sem quebrar versões existentes;
- definir defaults: agentes atuais permanecem em `llm`.

### 2. Motor de processo no worker

- criar uma máquina de estados pequena e determinística;
- manter estado por chamada, nunca globalmente;
- normalizar intenção e resposta do STT;
- executar transições somente permitidas;
- registrar cada transição como evento auditável;
- impedir loop, estado inexistente e transição ambígua.

### 3. Integração com ferramentas

- mapear ações configuradas para ferramentas existentes;
- exigir confirmação para ações com efeito;
- tratar `end_call` como ação terminal real;
- garantir que encerramento desconecte a sala e finalize a chamada.

### 4. Modo híbrido

- tentar intenção/regra local primeiro;
- chamar LLM apenas quando a política permitir;
- limitar a resposta da LLM ao estado atual;
- registrar motivo, modelo e custo do escalonamento;
- não alternar provedor durante um turno sem regra explícita.

### 5. Interface administrativa

- editor de etapas e transições;
- seleção do modo de execução;
- configuração de respostas, idioma, voz e provedores;
- validação visual antes de publicar;
- simulação de cada caminho;
- histórico e publicação de versões.

### 6. Observabilidade e documentação

- métricas por modo, estado, intenção e escalonamento;
- tempos separados de STT, decisão, LLM e TTS;
- motivo de encerramento e estado final;
- documentação de configuração e exemplos por segmento.

## Plano de testes

### Testes unitários

- transição válida e inválida;
- intenção desconhecida;
- estado terminal;
- confirmação obrigatória;
- timeout e silêncio;
- variáveis preenchidas na resposta;
- configuração incompleta ou cíclica;
- fallback controlado para LLM.

### Testes de integração

- carregar uma versão publicada no endpoint interno;
- iniciar sessão LiveKit e criar chamada;
- processar STT -> regra -> TTS;
- executar ferramenta e registrar tool call;
- encerrar e desconectar a sala;
- verificar persistência de eventos e turnos.

### Testes E2E de homologação

1. Saudação e confirmação.
2. Coleta de nome/telefone.
3. Agendamento, alteração e cancelamento.
4. Pedido fora do escopo.
5. Pergunta que exige LLM.
6. Transferência para atendente.
7. “Até logo” e encerramento efetivo.
8. Interrupção durante a fala.
9. Recarregamento/queda do navegador.
10. Ausência de uma chave opcional.

## Critérios de aceite

- um administrador cria e publica um processo sem editar código;
- o modo `deterministic` não chama LLM para caminhos conhecidos;
- o modo `hybrid` chama LLM somente conforme a política publicada;
- idioma, voz e provedor permanecem estáveis durante a chamada;
- cada transição é auditável;
- ações críticas exigem confirmação;
- `end_call` encerra áudio, sala e registro da chamada;
- agentes existentes continuam funcionando sem migração manual;
- uma configuração inválida não pode ser publicada.

## Requisitos para produto comercial

O motor de processos é o núcleo funcional, mas a entrega como SaaS também exige:

- isolamento rigoroso de tenant em processos, chamadas, documentos e métricas;
- permissões para editar, revisar, publicar e reverter versões;
- rascunho, validação, publicação e rollback sem interromper chamadas ativas;
- limites de chamadas, minutos, armazenamento e escalonamentos por plano;
- auditoria de alterações e de cada ação executada pelo agente;
- idempotência para webhooks, ferramentas e encerramento;
- observabilidade de disponibilidade, latência, custos e falhas por provedor;
- proteção de credenciais, dados pessoais e gravações;
- exportação/importação de processos para homologação e produção;
- testes de carga, recuperação após falha e política de retenção;
- documentação de operação, suporte e resposta a incidentes.

Esses requisitos devem ser tratados como parte do produto, e não como configuração específica de um cliente.

## Estimativa

- MVP funcional: 7–10 dias úteis;
- versão de produto com editor, versionamento, auditoria e cobertura E2E: 3–5 semanas.

A estimativa pressupõe reaproveitamento do LiveKit, STT, TTS, ferramentas e persistência atuais.

## Decisões importantes

- não remover o modo `llm` atual;
- não esconder falhas de provedor com alternância silenciosa;
- selecionar provedor por configuração e usar fallback apenas quando explicitamente permitido;
- tratar a base de conhecimento como capacidade opcional;
- manter respostas operacionais curtas e em idioma configurado;
- medir latência por componente antes de atribuí-la ao hardware local.

## Estado atual e próximo passo

O VoiceOS já possui configuração de idioma, LLM, STT, TTS, ferramentas, versão de agente e sessão LiveKit. Ainda falta transformar essas configurações em um motor de processo independente da LLM.

### Implementado nesta execução

- `voiceos_voice.flow.FlowEngine` com estados, transições, intenções e estado terminal;
- validação de `behavior.execution_mode` na API;
- validação de estados e destinos de transição antes de aceitar um draft;
- execução determinística no worker sem inicializar LLM;
- execução híbrida no worker: intenções conhecidas são resolvidas localmente e as demais são delegadas à LLM;
- correspondência local de intenções por exemplos configurados;
- adaptador LiveKit que mantém a decisão local dentro do ciclo normal de turnos;
- fallback inicial único para OpenAI Whisper quando Deepgram não estiver disponível;
- seleção fixa do provedor configurado para LLM e TTS;
- testes unitários do motor e regressão da pipeline de provedores.

Próximo passo recomendado: adicionar publicação/rollback e permissões específicas para processos, além de executar testes E2E de chamadas com fluxos publicados.

## Handoff técnico para outra equipe ou IA

### Regra de execução do GOAL

Ao iniciar este objetivo, a equipe ou IA deve tratar as decisões abaixo como já aprovadas. Não deve pausar para pedir confirmação sobre elas; deve implementar, testar, registrar evidências e somente interromper em caso de bloqueio real, risco de perda de dados ou conflito com uma decisão registrada.

O trabalho deve ser conduzido de forma incremental: preservar o modo atual, implementar atrás de feature flag, executar testes, corrigir regressões e deixar o repositório em estado reproduzível.

### Decisões já tomadas

- o produto será configurável por cliente e por versão de agente;
- processos operacionais devem funcionar sem LLM quando as regras forem suficientes;
- haverá modos `deterministic`, `hybrid` e `llm`;
- agentes existentes permanecem em `llm` por compatibilidade;
- o modo híbrido usa regras primeiro e LLM apenas por política explícita;
- idioma e voz são propriedades da configuração publicada, não decisões do modelo;
- não deve haver alternância silenciosa de idioma, voz ou provedor durante uma chamada;
- fallback só pode ocorrer no início da sessão, quando o provedor configurado estiver indisponível, e deve ser registrado;
- `end_call` é uma ação terminal que deve falar a despedida, desconectar a sala e finalizar o registro;
- a base de conhecimento é opcional e só deve ser consultada quando o processo exigir;
- ações com efeito exigem confirmação antes da execução;
- a UI é administrativa: editar, validar, simular, publicar e reverter versões;
- o ambiente local de homologação usa Docker em `G:\DEV\VOICE_OS` e credenciais do Windows Credential Manager;
- mudanças de produto devem ser commitadas e documentadas após os testes, sem incluir segredos.

### Premissas técnicas para não rediscutir

- LiveKit permanece como transporte de áudio e sessão;
- STT e TTS permanecem abstraídos por provedor configurável;
- o worker continua sendo o executor da chamada;
- a API continua sendo a autoridade de configuração, publicação e auditoria;
- PostgreSQL continua sendo a persistência principal;
- Redis continua disponível para cache/coordenação;
- qualquer dado ausente deve receber default compatível ou gerar erro de validação explícito;
- performance deve ser medida por componente antes de trocar provedores ou atribuir o problema ao hardware.

### Decisões que podem ser feitas autonomamente

A equipe pode escolher nomes de tabelas, classes, endpoints auxiliares, componentes visuais, estratégia interna de parsing e detalhes de implementação, desde que preserve os contratos, decisões e critérios deste documento. Toda escolha relevante deve ser registrada na seção de decisões do documento ou em um ADR vinculado.

### Condições que exigem parada

A execução só deve ser interrompida para decisão do responsável quando houver: alteração incompatível de contrato público; risco de expor credenciais ou dados de clientes; operação destrutiva sem recuperação; custo externo não previsto; ou conflito entre requisitos documentados. Dúvidas normais de implementação devem ser resolvidas pela opção mais conservadora e compatível, com registro posterior.

### Pontos de integração existentes

- API e contratos: `apps/api/voiceos_api/routes.py` e `schemas.py`;
- persistência e versões: `apps/api/voiceos_api/repository.py`;
- emissão/encerramento de sessões: `apps/api/voiceos_api/livekit_sessions.py`;
- runtime consumido pelo worker: endpoint interno de agentes em `routes.py`;
- execução de voz: `apps/agent-worker/voiceos_voice/livekit_worker.py`;
- prompt e regras gerais: `apps/agent-worker/voiceos_voice/prompting.py`;
- ciclo de turno e ferramentas: `apps/agent-worker/voiceos_voice/session.py`;
- ponte de chamadas e registro: `apps/agent-worker/voiceos_voice/runtime.py`;
- interface do teste: `apps/web/app/app/[tenantSlug]/voice-widget.tsx`;
- banco e migrações: `apps/api/alembic/` e `infra/`.

### Contrato de execução esperado

O endpoint interno deve entregar ao worker, no mínimo:

```json
{
  "agent_id": "uuid",
  "version_id": "uuid",
  "tenant_id": "uuid",
  "language": "pt-BR",
  "execution_mode": "deterministic",
  "states": [],
  "intents": [],
  "llm_policy": {},
  "llm": {},
  "stt": {},
  "tts": {},
  "turn": {},
  "behavior": {},
  "tools": []
}
```

O worker deve rejeitar configuração inválida antes de conectar o agente à sala. O estado atual deve ser mantido no contexto da chamada e enviado nos eventos de auditoria.

### Ordem segura de implementação

1. Criar schema e migração compatíveis com versões existentes.
2. Implementar parser/validador de fluxo sem LiveKit.
3. Implementar máquina de estados e testes unitários.
4. Integrar o dispatcher ao `AgentSession` atual.
5. Integrar ferramentas e `end_call` terminal.
6. Adicionar política de escalonamento para LLM.
7. Expor criação/edição/validação/publicação na API.
8. Adicionar editor e simulador na UI.
9. Executar testes de integração e E2E.
10. Publicar atrás de feature flag e medir latência/custo.

### Comandos de verificação

```text
pytest -q
ruff check .
docker compose -f G:\DEV\VOICE_OS\docker-compose.yml ps
docker compose -f G:\DEV\VOICE_OS\docker-compose.yml logs --tail=100 agent-worker
```

Uma implementação só deve ser considerada concluída quando os critérios de aceite forem demonstrados por testes ou evidência de homologação, e não apenas quando o código compilar.
