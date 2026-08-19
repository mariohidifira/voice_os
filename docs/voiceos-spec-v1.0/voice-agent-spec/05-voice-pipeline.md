# 05 — Pipeline de Voz (agent-worker)

Implementado com LiveKit Agents SDK (Python). Um `AgentSession` por room. Este arquivo define comportamento; o SDK provê a mecânica.

## Componentes por sessão

```
Audio in (48k web / 8k phone) → AEC/NS (LiveKit) → Silero VAD → Deepgram STT (streaming, interim+final)
   → Turn detector (fim de turno) → LLM (Claude, streaming, tools) → sentence chunker
   → ElevenLabs TTS (streaming) → Audio out
```

## Configuração padrão por canal

| Parâmetro | Web | Telefone |
|---|---|---|
| Sample rate in/out | 48 kHz Opus | 8 kHz PCMU (SIP) |
| STT model | `nova-3` language `pt-BR`, `interim_results=true`, `smart_format=true`, `endpointing=300ms`, `utterance_end_ms=1000` | idem, `keywords` do agente |
| VAD | Silero, `min_speech_duration=0.05s`, `min_silence_duration=0.55s`, `activation_threshold=0.5` | `min_silence_duration=0.7s` |
| Turn detection | `min_endpointing_delay=0.5s`, `max_endpointing_delay=3.0s` (modelo de turn do LiveKit decide dentro dessa faixa) | `min=0.6s`, `max=3.5s` |
| Interrupções | `allow_interruptions=true`, `min_interruption_duration=0.5s`, `min_interruption_words=1` | `min_interruption_duration=0.6s`, `min_interruption_words=2` (mais ruído na linha) |
| TTS | `eleven_flash_v2_5`, `optimize_streaming_latency=3`, `stability=0.5`, `similarity=0.75` | idem, saída reamostrada para 8 kHz |
| LLM | `claude-sonnet-<latest>`, `temperature=0.3`, `max_tokens=350` por turno, streaming | idem |
| Silêncio do usuário | 8 s → fala `behavior.silence_prompt`; 2 vezes → encerra | 10 s |
| Duração máxima | `behavior.max_call_duration_s` (default 900) | idem |

Todos sobrescritíveis por `agent_versions.stt/tts/turn/behavior`.

## Ciclo de vida da sessão

1. **Dispatch**: worker recebe job com room metadata `{tenant_id, agent_id, version, channel, call_id?, from, to, variables, end_user}`.
2. **Load**: `GET /internal/agents/{id}/runtime` (cache Redis 60 s). Se falhar 3× → entra na room, fala mensagem de erro fixa em pt-BR e encerra; registra `call.failed`.
3. **Prewarm**: abrir conexões STT e TTS antes do participante entrar (reduz TTFB da saudação).
4. **Join**: `POST /internal/calls` (ou `PATCH` se já criado por outbound). Aguarda participante. Timeout 30 s → encerra.
5. **Greeting**: TTS de `greeting` renderizado. Em outbound telefone: espera 0,8 s de áudio do outro lado (ou AMD) antes de falar.
6. **Loop de turnos** (abaixo).
7. **Encerramento**: por tool `end_call`, frase de encerramento, silêncio, hangup remoto, duração máxima ou erro. Fala despedida se aplicável, espera TTS terminar, sai da room, `PATCH /internal/calls/{id}` com `ended_at`, `end_reason`, custos e latências agregadas.

## Loop de turnos

```
on user speech start  → publica evento; se agente falando → BARGE-IN
on interim transcript → nada (opcionalmente pré-busca RAG se > 5 palavras)
on final transcript + turn detector diz "fim de turno":
   1. monta contexto (histórico + RAG se habilitado + variáveis)
   2. se tools que demoram (>800 ms típico) provável → filler
   3. LLM streaming
      - texto → sentence chunker → TTS (primeira frase sai antes da resposta completa)
      - tool_use → executa (ver 06); se tool tem speak_before, fala; resultado volta ao LLM; continua streaming
   4. publica turn.agent com ttfb_ms
```

### Barge-in (interrupção)
Ordem exata quando VAD detecta fala do usuário enquanto o agente fala, respeitados `min_interruption_duration/words`:
1. Para reprodução de áudio imediatamente (flush do buffer de saída).
2. Cancela stream TTS em andamento.
3. Cancela geração LLM em andamento (`abort`).
4. Trunca o turno do agente no histórico para o texto **efetivamente falado** (o SDK expõe o transcript sincronizado com o áudio). Marca `interrupted=true`.
5. Publica `barge_in` com `{spoken_chars, total_chars}`.
6. Continua ouvindo o novo turno do usuário normalmente.
Meta: RNF-03 ≤ 300 ms do início da fala até silêncio do agente.

Falsos positivos (tosse, "hum"): mitigado por `min_interruption_words` (precisa de ao menos N palavras transcritas) e por lista de backchannels ignorados: `["hum", "uhum", "sim", "tá", "ok", "certo", "aham"]` quando isolados e o agente ainda está falando. Configurável em `turn.ignore_backchannels`.

### Filler (evita silêncio em tool lenta)
Se a tool chamada tem `speak_before`, fala esse texto. Senão, se `behavior.filler_enabled`, após 600 ms sem primeiro token/áudio, fala uma frase aleatória de `behavior.filler_phrases` (default: `["Só um instante.", "Deixa eu verificar.", "Um momento, por favor."]`). Nunca fala filler duas vezes seguidas.

### Troca de contexto no meio
Não há máquina de estados. O histórico completo vai ao LLM a cada turno; o prompt instrui a priorizar o pedido mais recente (`07-prompts.md`). Se o usuário mudar de assunto durante uma tool assíncrona, o resultado da tool ainda entra no histórico como `tool_result` e o LLM decide se menciona.

### RAG
Se `rag.enabled`: a cada turno do usuário, embedding da última mensagem (mais a anterior se < 6 palavras) → `POST /internal/rag/query` `top_k=rag.top_k (5)`, `min_score=0.35` → injeta como bloco `<knowledge>` no turno atual (não no system prompt), limitado a `rag.max_tokens (1200)`. Orçamento de latência: 250 ms; se estourar, segue sem RAG e registra evento.

### Contexto e memória
- Histórico completo em memória durante a chamada. Se passar de 60 mensagens ou 12k tokens, resumir os turnos mais antigos com o LLM (job em background, sem bloquear) e substituir por um `system` de resumo.
- Variáveis (`set_variable` tool ou extraídas) ficam em `session.variables` e vão em `calls.variables` ao final.

## Latência: orçamento por etapa (alvo p50, web)

| Etapa | Meta |
|---|---|
| Fim da fala → final transcript | 250 ms |
| Turn detection | 200 ms |
| RAG (paralelo com preparação) | 250 ms |
| LLM primeiro token | 350 ms |
| Primeira frase → TTS primeiro byte | 200 ms |
| **Total voz-para-voz** | **~900 ms** |

Instrumentar cada etapa com spans OpenTelemetry (`12-observabilidade.md`). Registrar `ttfb_ms` por turno.

## Fallbacks e resiliência

| Falha | Ação |
|---|---|
| STT sem resposta 3 s | reconectar; 2ª falha → trocar para provider fallback (Whisper) na mesma sessão |
| LLM erro 5xx/timeout 8 s | retry 1× ; depois fallback provider (OpenAI) com mesmo prompt e tools; evento `error` |
| LLM rate limit 429 | fallback provider imediato |
| TTS erro | retry 1×; fallback Cartesia; se falhar, fala nada e registra |
| Tool timeout (`webhook.timeout_ms`, default 8 s) | retorna `{"error":"timeout"}` ao LLM; prompt instrui a avisar o usuário |
| Perda de conexão do participante | espera 15 s reconexão; depois encerra `end_reason=user_hangup` |
| Runtime config indisponível | mensagem de erro fixa e encerra |

Circuit breaker por provider (5 falhas em 60 s → aberto por 120 s → half-open).

## Áudio
- AEC e supressão de ruído do lado do cliente (WebRTC nativo) e `noise_cancellation` do LiveKit no agente.
- Telefone: aplicar ganho normalizado (`-16 LUFS`) na saída TTS antes de reamostrar.
- Gravação: LiveKit Egress `room composite audio-only` → `ogg` no S3 `recordings/{tenant_id}/{call_id}.ogg`, iniciado ao `call.answered` se `tenants.settings.recording_enabled`. Aviso de gravação: se `settings.recording_notice = true`, a saudação é prefixada com `"Esta ligação pode ser gravada."` (texto configurável).

## Métricas por chamada gravadas
`latency.ttfb_p50_ms`, `ttfb_p95_ms`, `turns`, `barge_ins`, `stt_reconnects`, `llm_fallbacks`, `tts_fallbacks`, `tool_calls`, `tool_errors`, `rag_queries`, `cost.*`.

## Cálculo de custo (por chamada)
- STT: minutos de áudio de entrada × preço Deepgram
- LLM: tokens in/out por turno × preço do modelo (tabela `provider_prices` em config, atualizada por deploy)
- TTS: caracteres sintetizados × preço
- Telefonia: minutos × preço Twilio (in/out) — só telefone
- LiveKit: minutos de participante × preço
Guardar em `calls.cost` em USD com 4 casas.
