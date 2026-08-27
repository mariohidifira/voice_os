# 09 — Canais

## WebRTC (web/app) — Fase 1
- `POST /v1/sessions` com API key pública → token LiveKit (identity `user_<end_user_id|uuid>`, room `call_<uuid>`, grants: publish audio, subscribe).
- Room metadata: `{tenant_id, agent_id, version, channel:"web", call_id, variables, end_user}`.
- Dispatch: `agent dispatch` explícito ao criar a room (`RoomService.create_room` + `AgentDispatch.create_dispatch` com `agent_name="voiceos-agent"`).
- Cliente: LiveKit JS SDK; pedir permissão de microfone; publicar track com `echoCancellation`, `noiseSuppression`, `autoGainControl` on.
- Fim: cliente sai da room ou `DELETE /v1/sessions/{id}`; room `empty_timeout=30s`.
- Segurança: allowlist de origens na API key; token TTL 1 h; uma sessão por token.
- Fase 5: `packages/widget` gera `voiceos.js` (`<script type="module" src=... data-agent-id=... data-key=vos_pk_... data-api-url=.../v1/public/tenants/{tenant_id}/widget/sessions>`), botão flutuante, temas, posição, eventos JS (`voiceos:start`, `voiceos:end`), e SDK npm `@voiceos/web` com `livekitModuleUrl` opcional para bundle browser pinado/self-hosted.

## Telefone (PSTN) — Fase 2

### Setup (uma vez, via Terraform + script)
1. Twilio: criar Elastic SIP Trunk `voiceos-{env}`; origination URI = LiveKit SIP endpoint; termination com credenciais; habilitar gravação off (gravamos no LiveKit).
2. LiveKit: `SIPInboundTrunk` (números aceitos = todos comprados; auth por IP/credenciais Twilio) e `SIPOutboundTrunk` (address = `{TWILIO_SIP_DOMAIN}`, auth user/pass, numbers = comprados).
3. Dispatch rule por número: ao comprar (`POST /v1/phone-numbers`), a API cria `SIPDispatchRule` do tipo `individual` com `room_prefix="call_"`, metadata `{tenant_id, agent_id}` e `agent_name="voiceos-agent"`. Ao reatribuir número, atualiza a rule.

### Inbound
Twilio → SIP INVITE → LiveKit cria room, participante SIP entra → dispatch → agent-worker. Metadata da room traz `sip.trunkPhoneNumber` (destino) e `sip.phoneNumber` (origem); worker resolve `agent_id` pela dispatch rule metadata e cria `calls` com `channel=phone_inbound`.
Fora do horário (`behavior.business_hours`): agente atende, fala `out_of_hours_message`, opcionalmente coleta recado (variáveis) e encerra.

### Outbound
`POST /v1/calls/outbound` → API cria room, dispatch do agente com metadata `{..., channel:"phone_outbound", to}`; agente ao iniciar chama `CreateSIPParticipant` (trunk outbound, `to`, `from` = número do agente, `wait_until_answered=true`, `play_dialtone=false`, `krisp_enabled=true`). Estados mapeados de SIP para `calls.status`: ringing → in_progress (answered) / no_answer / busy / failed. Timeout de ring 30 s.
AMD: habilitar detecção do Twilio (`MachineDetection=DetectMessageEnd` via header SIP `X-Twilio-...` não disponível em SIP trunk puro) → **usar classificação por transcrição** (`07`) nos primeiros 4 s + heurística de silêncio/beep. Se `voicemail`: falar `behavior.voicemail_message` após beep detectado (VAD silêncio ≥ 1,5 s) e encerrar `end_reason=voicemail_left`.

### Campanhas
`worker` job `campaign_runner`: a cada 30 s pega contatos `pending|retry` com `next_attempt_at <= now`, respeita `window`, `days`, `timezone`, `max_concurrency` (conta calls `in_progress|ringing` da campanha) e limite do plano; cria outbound; atualiza contato conforme resultado; retry por `retry_policy` só para `no_answer|busy|failed`.
Compliance: bloquear horários fora de 8h–20h no fuso do contato; lista de bloqueio por tenant (`do_not_call` phones); opt-out por frase ("não me ligue mais") → tool `set_variable(opt_out=true)` → adiciona à lista.

### Transferência
- **Cold**: `transfer_sip_participant` (SIP REFER) para `destination`. Agente sai.
- **Warm**: agente cria segundo participante SIP (`destination`), fala resumo de 1 frase quando atender, depois faz `mute` de si e sai; os dois humanos ficam na room. Se destino não atende em 25 s, agente volta e informa.

### SMS
Twilio Messaging Service com o número do agente; `send_sms` tool; status callback em `/webhooks/twilio/sms-status`. Só números com capability SMS (BR: exige long code habilitado; documentar limitação).

### Qualidade
Reamostragem 8 kHz, ganho, `krisp` on. Métrica de MOS estimado a partir de stats RTP do LiveKit (packet loss, jitter) por chamada em `calls.latency.network`.

## WhatsApp — Fase 4
Via WhatsApp Cloud API (Meta). Tenant conecta número em `/settings/integrations` (Embedded Signup ou token manual). Webhook em `/webhooks/whatsapp`.

Fluxo (não é tempo real):
1. Mensagem recebida (`text` ou `audio`). Áudio: baixar mídia (ogg/opus) → STT batch (Deepgram pre-recorded).
2. Conversa mapeada em `calls` com `channel=whatsapp`, uma "call" por janela de 24 h por número; turnos em `call_turns`.
3. LLM com mesmo prompt/tools/RAG (sem regras de voz? **manter**, respostas curtas são adequadas). Marcar "digitando" via API.
4. Resposta: texto sempre; se a mensagem do usuário foi áudio, também enviar áudio TTS (ogg/opus). Configurável em `behavior.whatsapp_reply_mode: text|audio|both`.
5. Tools funcionam igual. `end_call` fecha a "call" lógica. `transfer_call` → notifica operador (`/live`) para assumir a conversa por texto (handoff humano no painel, Fase 4).
6. Templates de mensagem (HSM) para iniciar conversa fora da janela (campanhas WhatsApp): fora do escopo v1, deixar tabela `whatsapp_templates` prevista.

Limites: mídia até 16 MB; áudio TTS ≤ 60 s por mensagem (dividir se maior).
