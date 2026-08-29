"use client";

import { Room, RoomEvent, Track, type RemoteTrack } from "livekit-client";
import { useEffect, useRef, useState } from "react";

type Session = { session_id: string; call_id: string; livekit_url: string; token: string };

export default function VoiceWidget({ agentId, language, onClose, onNotice }: { agentId: string; language?: string; onClose: () => void; onNotice: (message: string) => void }) {
  const [state, setState] = useState<"ready" | "connecting" | "connected" | "ended" | "error">("ready");
  const [muted, setMuted] = useState(false);
  const [level, setLevel] = useState(0);
  const roomRef = useRef<Room | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const closingRef = useRef(false);
  const connectedRef = useRef(false);
  const audioRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => { void roomRef.current?.disconnect(); }, []);

  async function start() {
    setState("connecting");
    try {
      const response = await fetch(`/api/voiceos/agents/${agentId}/test-session`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, variables: {}, metadata: { source: "entry_point", language: language ?? "pt-BR" } }),
      });
      if (!response.ok) throw new Error((await response.json().catch(() => ({})))?.detail?.message ?? `HTTP ${response.status}`);
      const session = await response.json() as Session;
      sessionRef.current = session;
      const room = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;
      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === Track.Kind.Audio && audioRef.current) audioRef.current.appendChild(track.attach());
      });
      room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => track.detach().forEach((element) => element.remove()));
      room.on(RoomEvent.Disconnected, () => {
        if (closingRef.current) return;
        if (!connectedRef.current) {
          setState("error");
          onNotice("A sala foi desconectada antes de iniciar a conversa.");
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
      setState("error");
      onNotice(error instanceof Error ? error.message : "Não foi possível conectar ao teste de voz");
    }
  }

  async function toggleMute() {
    const room = roomRef.current; if (!room) return;
    await room.localParticipant.setMicrophoneEnabled(muted);
    setMuted(!muted);
  }

  async function end() {
    closingRef.current = true;
    const room = roomRef.current;
    await room?.localParticipant.setMicrophoneEnabled(false);
    await room?.disconnect();
    if (sessionRef.current) await fetch(`/api/voiceos/sessions/${sessionRef.current.session_id}`, { method: "DELETE" });
    setState("ended");
    onNotice("Teste encerrado; a chamada e a transcrição já estão disponíveis.");
  }

  return <div className="modal" role="dialog" aria-modal="true" aria-label="Teste de voz">
    <div className="voiceWidget card"><div className="editorHead"><div><div className="eyebrow">teste WebRTC</div><h2>Converse com o rascunho</h2></div><button className="close" onClick={async () => { await end(); onClose(); }}>×</button></div>
      <div className={`orb ${state}`} style={{ "--level": Math.max(.05, level) } as React.CSSProperties}><span/></div>
      <p className="voiceState">{state === "ready" ? "Pronto para acessar seu microfone" : state === "connecting" ? "Conectando à sala segura…" : state === "connected" ? (muted ? "Microfone pausado" : "Ouvindo — pode falar") : state === "ended" ? "Chamada encerrada" : "Falha na conexão"}</p>
      <div ref={audioRef} className="remoteAudio"/>
      <div className="voiceActions">{state === "ready" && <button onClick={() => void start()}>Iniciar conversa</button>}{state === "connected" && <><button className="secondary" onClick={() => void toggleMute()}>{muted ? "Ativar microfone" : "Silenciar"}</button><button className="danger" onClick={() => void end()}>Encerrar</button></>}{["ended", "error"].includes(state) && <button onClick={onClose}>Fechar</button>}</div>
      <small>O navegador solicitará permissão de microfone. Use fones para melhor cancelamento de eco.</small>
    </div>
  </div>;
}
