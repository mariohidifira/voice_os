# 15 — Glossário

| Termo | Significado |
|---|---|
| Agent | Configuração de um agente de voz (prompt, voz, tools, KB) pertencente a um tenant |
| Agent version | Snapshot imutável publicado de um agent |
| AMD | Answering Machine Detection — detectar secretária eletrônica em outbound |
| Barge-in | Usuário fala por cima do agente; o agente para de falar e escuta |
| Backchannel | Sons curtos de acompanhamento ("uhum", "sim") que não são interrupção |
| Call | Uma conversa (web, telefone ou janela de WhatsApp) com transcrição, eventos e custo |
| Dispatch rule | Regra do LiveKit que decide qual agente entra em qual room ao receber SIP/sessão |
| Endpointing | Decidir que o usuário terminou de falar |
| Egress | Gravação/exportação de mídia de uma room do LiveKit |
| End user | Pessoa que conversa com o agente (não é usuário do painel) |
| Filler | Frase curta dita enquanto uma tool demora ("um instante") |
| KB | Knowledge base — documentos indexados para RAG |
| LiveKit | Infraestrutura WebRTC/SIP e SDK de agentes usados no pipeline |
| PSTN | Rede telefônica pública |
| RAG | Retrieval-augmented generation — buscar trechos relevantes e injetar no contexto do LLM |
| RLS | Row Level Security do Postgres |
| Room | Sala do LiveKit onde agente e usuário trocam áudio |
| SIP trunk | Conexão entre operadora (Twilio) e o LiveKit para chamadas telefônicas |
| STT | Speech-to-text (Deepgram) |
| Tenant | Cliente da plataforma (empresa); unidade de isolamento de dados |
| Tool | Função que o LLM pode chamar (nativa ou webhook do cliente) |
| TTFB | Time to first byte — aqui, tempo até o primeiro áudio do agente após o usuário parar de falar |
| TTS | Text-to-speech (ElevenLabs) |
| Turn | Uma fala completa do usuário ou do agente |
| Turn detection | Modelo/heurística que decide o fim do turno do usuário |
| VAD | Voice Activity Detection — detecta presença de fala no áudio |
| Warm/cold transfer | Transferência com apresentação prévia ao humano / direta |
