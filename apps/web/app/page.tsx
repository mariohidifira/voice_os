"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const languages = [["pt-BR", "Português (Brasil)"], ["en-US", "English (US)"], ["es-ES", "Español"]] as const;

function RingTone({ active }: { active: boolean }) {
  const contextRef = useRef<AudioContext | null>(null);
  const timerRef = useRef<number | null>(null);
  useEffect(() => () => { if (timerRef.current) window.clearInterval(timerRef.current); void contextRef.current?.close(); }, []);
  useEffect(() => {
    if (!active) return;
    const AudioContextClass = window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass(); contextRef.current = ctx;
    const ring = () => { const osc = ctx.createOscillator(); const gain = ctx.createGain(); osc.frequency.value = 740; gain.gain.setValueAtTime(0.0001, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.06, ctx.currentTime + 0.03); gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.52); osc.connect(gain).connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.55); };
    ring(); timerRef.current = window.setInterval(ring, 1800);
    return () => { if (timerRef.current) window.clearInterval(timerRef.current); void ctx.close(); contextRef.current = null; };
  }, [active]);
  return null;
}

export default function Home() {
  const router = useRouter();
  const [language, setLanguage] = useState("pt-BR");
  const [calling, setCalling] = useState(false);
  useEffect(() => { const saved = window.localStorage.getItem("voiceos-language"); if (saved) setLanguage(saved); }, []);
  function chooseLanguage(value: string) { setLanguage(value); window.localStorage.setItem("voiceos-language", value); }
  function accept() { router.push(`/app/demo?entry=agent&lang=${encodeURIComponent(language)}`); }
  return <main className="entryShell"><RingTone active={calling} /><div className="entryGrid">
    <section className="entryHero"><div className="entryBrand"><span className="entryPulse" /> VOICE<span>/</span>OS</div><div className="eyebrow">Conversational operations</div><h1>Uma presença inteligente<br /><span>em cada chamada.</span></h1><p className="entryLead">Demonstre a experiência, configure a operação e conecte uma atendente cordial em poucos passos.</p><label className="entryLanguage">Idioma da experiência<select value={language} onChange={(event) => chooseLanguage(event.target.value)}>{languages.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label></section>
    <section className="entryActions" aria-label="Escolha uma experiência">{!calling ? <><button className="entryButton entryAdmin" onClick={() => router.push("/app/demo")}><span className="entryIcon">⌘</span><span><strong>Dashboard administrativo</strong><small>Configure agentes, voz, ferramentas e governança.</small></span><b>→</b></button><button className="entryButton entryAgent" onClick={() => setCalling(true)}><span className="entryIcon">◉</span><span><strong>Falar com o agente</strong><small>Inicie uma demonstração guiada por voz.</small></span><b>→</b></button></> : <div className="incomingCall" role="dialog" aria-modal="true" aria-label="Chamada recebida"><div className="callOrb"><span /></div><div className="eyebrow">VoiceOS secure line</div><h2>Ligando para o agente</h2><p>Atendente Ava · {languages.find(([value]) => value === language)?.[1]}</p><div className="callButtons"><button className="accept" onClick={accept}>Accept</button><button className="decline" onClick={() => setCalling(false)}>Decline</button></div><small>A atendente fará a saudação, confirmará o pedido e encerrará a chamada com cordialidade.</small></div>}</section>
  </div><footer className="entryFooter">LOCAL DEMO <span>•</span> WebRTC / LiveKit <span>•</span> {language}</footer></main>;
}
