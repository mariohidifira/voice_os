"use client";

import { Room, RoomEvent, Track, type RemoteTrack } from "livekit-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Session = { session_id: string; call_id: string; livekit_url: string; token: string };
type WidgetState = "ready" | "connecting" | "connected" | "ended" | "error";
type TranscriptLine = { role: "user" | "assistant"; text: string; interim?: boolean };

function Icon({ children }: { children: React.ReactNode }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{children}</svg>;
}

export default function VoiceWidget({ agentId, language = "pt-BR", autoStart = false, fullPage = false, onClose, onNotice }: { agentId: string; language?: string; autoStart?: boolean; fullPage?: boolean; onClose: () => void; onNotice: (message: string) => void }) {
  const [state, setState] = useState<WidgetState>("ready");
  const [muted, setMuted] = useState(false);
  const [speakerMuted, setSpeakerMuted] = useState(false);
  const [level, setLevel] = useState(0);
  const [errorDetail, setErrorDetail] = useState("");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const roomRef = useRef<Room | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const transcriptSourceRef = useRef<EventSource | null>(null);
  const closingRef = useRef(false);
  const connectedRef = useRef(false);
  const audioRef = useRef<HTMLDivElement>(null);

  const closeLiveStream = useCallback(() => {
    transcriptSourceRef.current?.close();
    transcriptSourceRef.current = null;
  }, []);

  useEffect(() => () => {
    closeLiveStream();
    void roomRef.current?.disconnect();
  }, [closeLiveStream]);

  const addTranscript = useCallback((role: TranscriptLine["role"], text: string, interim = false) => {
    setTranscript((lines) => {
      const last = lines.at(-1);
      if (last?.role === role && last.text === text && last.interim === interim) return lines;
      if (role === "user" && last?.role === "user" && last.interim) return [...lines.slice(0, -1), { role, text, interim }];
      return [...lines, { role, text, interim }];
    });
  }, []);

  const start = useCallback(async () => {
    if (roomRef.current || closingRef.current) return;
    setState("connecting");
    setErrorDetail("");
    try {
      const response = await fetch(`/api/voiceos/agents/${agentId}/test-session`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, variables: {}, metadata: { source: "entry_point", language } }),
      });
      if (!response.ok) throw new Error((await response.json().catch(() => ({})))?.detail?.message ?? `HTTP ${response.status}`);
      const session = await response.json() as Session;
      sessionRef.current = session;
      setTranscript([]);

      const transcriptSource = new EventSource(`/api/voiceos/calls/${session.call_id}/live`);
      transcriptSourceRef.current = transcriptSource;
      transcriptSource.onmessage = (event) => {
        const item = JSON.parse(event.data) as Record<string, unknown>;
        const type = String(item.type ?? "");
        if (type === "stt.interim" || type === "stt.final") {
          const text = String(((item.payload ?? {}) as Record<string, unknown>).text ?? "").trim();
          if (text) addTranscript("user", text, type === "stt.interim");
          return;
        }
        if (type === "turn.user" || type === "turn.assistant") {
          const turn = (item.turn ?? {}) as Record<string, unknown>;
          const text = String(turn.text ?? "").trim();
          if (text) addTranscript(type === "turn.user" ? "user" : "assistant", text);
        }
      };

      const room = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;
      const finishFromAgent = async () => {
        if (closingRef.current || !connectedRef.current) return;
        closingRef.current = true;
        await room.localParticipant.setMicrophoneEnabled(false).catch(() => undefined);
        await room.disconnect();
        closeLiveStream();
        if (sessionRef.current) await fetch(`/api/voiceos/sessions/${sessionRef.current.session_id}`, { method: "DELETE" });
        setState("ended");
        onNotice("A conversa foi encerrada pelo agente.");
        onClose();
      };

      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === Track.Kind.Audio && audioRef.current) {
          const audio = track.attach() as HTMLAudioElement;
          audio.muted = speakerMuted;
          audioRef.current.appendChild(audio);
        }
      });
      room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => track.detach().forEach((element) => element.remove()));
      room.on(RoomEvent.ParticipantDisconnected, () => void finishFromAgent());
      room.on(RoomEvent.Disconnected, () => {
        if (closingRef.current) return;
        closeLiveStream();
        if (!connectedRef.current) {
          setState("error");
          setErrorDetail("A sala de voz foi desconectada antes de iniciar.");
          onNotice("Não foi possível iniciar a conversa.");
          return;
        }
        closingRef.current = true;
        setState("ended");
        if (sessionRef.current) void fetch(`/api/voiceos/sessions/${sessionRef.current.session_id}`, { method: "DELETE" });
        onNotice("A conversa foi encerrada pelo agente.");
        onClose();
      });

      await room.connect(session.livekit_url, session.token, { autoSubscribe: true });
      await room.startAudio();
      await room.localParticipant.setMicrophoneEnabled(true, { echoCancellation: true, noiseSuppression: true, autoGainControl: true });
      connectedRef.current = true;
      setState("connected");
      const meter = window.setInterval(() => {
        const remote = Math.max(0, ...Array.from(room.remoteParticipants.values()).map((participant) => participant.audioLevel));
        setLevel(Math.max(room.localParticipant.audioLevel, remote));
      }, 100);
      room.once(RoomEvent.Disconnected, () => window.clearInterval(meter));
    } catch (error) {
      closeLiveStream();
      setState("error");
      const detail = error instanceof Error ? error.message : "erro desconhecido";
      setErrorDetail(detail);
      onNotice(`Falha na conexão: ${detail}`);
    }
  }, [addTranscript, agentId, closeLiveStream, language, onClose, onNotice, speakerMuted]);

  useEffect(() => { if (autoStart) void start(); }, [autoStart, start]);

  async function toggleMute() {
    const room = roomRef.current;
    if (!room) return;
    await room.localParticipant.setMicrophoneEnabled(muted);
    setMuted(!muted);
  }

  function toggleSpeaker() {
    const nextMuted = !speakerMuted;
    audioRef.current?.querySelectorAll("audio").forEach((audio) => { audio.muted = nextMuted; });
    setSpeakerMuted(nextMuted);
  }

  async function end() {
    if (closingRef.current) return;
    closingRef.current = true;
    const room = roomRef.current;
    await room?.localParticipant.setMicrophoneEnabled(false);
    await room?.disconnect();
    closeLiveStream();
    if (sessionRef.current) await fetch(`/api/voiceos/sessions/${sessionRef.current.session_id}`, { method: "DELETE" });
    setState("ended");
    onNotice("Conversa encerrada.");
    onClose();
  }

  const visibleTranscript = useMemo(() => transcript.slice(-4), [transcript]);
  const stateLabel = state === "ready" ? "Pronto para conversar" : state === "connecting" ? "Conectando ao agente" : state === "connected" ? (muted ? "Microfone pausado" : "Ouvindo…") : state === "ended" ? "Conversa encerrada" : "Não foi possível conectar";
  const stateSub = state === "connected" ? (muted ? "Ative o microfone para voltar à conversa" : "Fale naturalmente — o agente está prestando atenção") : state === "connecting" ? "Preparando voz, idioma e contexto" : "";
  const status = state === "connected" ? "Em atendimento" : state === "connecting" ? "Conectando" : "Sessão de voz";

  return <div className={fullPage ? "agentExperience" : "modal"} role="dialog" aria-modal="true" aria-label="Conversa com o agente">
    <div className={fullPage ? "voiceWidget voiceWidgetFull" : "voiceWidget card"}>
      <header className="sessionHeader">
        <div className="sessionBrand"><strong>VoiceOS</strong><span>/ sessão ativa</span></div>
        <div className="sessionMeta"><span className={state === "connected" ? "sessionChip active" : "sessionChip"}><i />{status}</span><button className="sessionClose" aria-label="Encerrar conversa" onClick={() => void end()}>×</button></div>
      </header>

      <main className="listenStage">
        <div className={`entryOrbButton sessionEntryOrb ${state}`} style={{ "--level": Math.max(.08, level) } as React.CSSProperties} aria-hidden="true"><span className="entryOrbCore" /><span className="entryOrbWave entryOrbWaveOne" /><span className="entryOrbWave entryOrbWaveTwo" /></div>
        <div className="listenCopy"><strong>{stateLabel}</strong></div>
        <div className="inlineTranscript" aria-live="polite">
          {!visibleTranscript.length && <span className="transcriptPlaceholder">{stateSub || "A conversa aparecerá aqui."}</span>}
          {visibleTranscript.map((line, index) => <p className={`${line.role}${line.interim ? " interim" : ""}`} key={`${index}-${line.text}`}><b>{line.role === "user" ? "Você" : "Agente"}</b>{line.text}</p>)}
        </div>
        <div className="callStatus"><strong>{status}</strong><span>{muted ? "Seu microfone está desativado" : "Áudio seguro e em tempo real"}</span></div>
        <div className="roundControls">
          {state === "ready" && <button className="roundControl primary" onClick={() => void start()}><span><Icon><path d="M8 5v14l11-7z" /></Icon></span><small>Iniciar</small></button>}
          {state === "connected" && <><button className={`roundControl ${muted ? "isMuted" : ""}`} onClick={() => void toggleMute()}><span><Icon><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" /><path d="M19 11a7 7 0 0 1-14 0M12 18v3M8 21h8" /></Icon></span><small>{muted ? "Ativar microfone" : "Silenciar microfone"}</small></button><button className={`roundControl ${speakerMuted ? "isMuted" : ""}`} onClick={toggleSpeaker}><span><Icon><path d="M4 10h4l5-4v12l-5-4H4z" /><path d={speakerMuted ? "M16 9l4 4m0-4-4 4" : "M16 9a5 5 0 0 1 0 6"} /></Icon></span><small>{speakerMuted ? "Ligar som" : "Desligar som"}</small></button></>}
          {state !== "error" && <button className="roundControl end" onClick={() => void end()}><span><Icon><path d="M8 8h8v8H8z" /></Icon></span><small>Encerrar</small></button>}
          {state === "error" && <button className="roundControl primary" onClick={onClose}><span><Icon><path d="M6 12h12M12 6l6 6-6 6" /></Icon></span><small>Voltar</small></button>}
        </div>
      </main>

      <div ref={audioRef} className="remoteAudio" />
      {errorDetail && state === "error" && <p className="fieldHint">Detalhe: {errorDetail}</p>}
    </div>
  </div>;
}
