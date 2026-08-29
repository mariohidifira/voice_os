# Análise de áudio do vídeo de referência

## Método

- Arquivo analisado: `docs/video.mp4`.
- Transcrição feita com OpenAI Whisper (`whisper-1`) após autorização explícita.
- O áudio e a transcrição foram mantidos somente em arquivos temporários e removidos ao final.
- Não foi gravado o conteúdo integral da conversa neste repositório.

## Resultado observado

- Duração do áudio: aproximadamente 6min15s.
- Idioma detectado: inglês (`english`) em toda a faixa; não houve evidência de alternância automática para português ou espanhol.
- Fluência: fala compreensível e contínua, mas com formulações repetidas e alguns termos reconhecidos de forma incorreta, provavelmente por ruído/TTS/contexto de domínio (por exemplo, “branch 20 hectares”).
- Pausas relevantes entre segmentos: 6; as maiores foram aproximadamente 8s e 6s. Isso é compatível com espera de ferramenta/API ou confirmação de ação, não com uma conversa de baixa fluência.
- Há repetição de detalhes do pedido 2252 e uma ação que termina como `Action cancelled`, indicando que o estado da ferramenta/encerramento precisa ser refletido claramente na UI.

## Implicações para o VoiceOS

1. O idioma deve ser uma configuração fixa da sessão (`pt-BR` por padrão), enviada de forma consistente para STT, prompt e TTS.
2. O painel deve mostrar estados distintos de `ouvindo`, `processando ferramenta`, `falando`, `aguardando confirmação` e `encerrado`.
3. A UI não deve permanecer ouvindo após `end_call` ou cancelamento; deve interromper captura, reprodução e sessão LiveKit.
4. Latência de ferramenta/API deve aparecer como estado explícito, com timeout e mensagem de recuperação, em vez de parecer silêncio.

Este relatório é evidência de diagnóstico do vídeo de referência, não um teste de produção do VoiceOS.
