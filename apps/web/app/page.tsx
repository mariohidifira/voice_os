"use client";

import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  const callAgent = () => {
    const context = new AudioContext();
    void context.resume();
    const ring = (when: number) => {
      [440, 480].forEach((frequency) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, context.currentTime + when);
        gain.gain.exponentialRampToValueAtTime(0.045, context.currentTime + when + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + when + 0.72);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start(context.currentTime + when);
        oscillator.stop(context.currentTime + when + 0.75);
      });
    };
    ring(1.4); ring(2.45);
    window.setTimeout(() => router.push("/app/demo?entry=agent&lang=pt-BR"), 2500);
  };

  return (
    <main className="entryShell">
      <section className="entrySimple" aria-labelledby="entry-title">
        <div className="entryProduct">Voice<span>OS</span></div>
        <div className="eyebrow">Atendimento inteligente</div>
        <h1 id="entry-title">Uma presença inteligente<span> em cada conversa.</span></h1>
        <p>Converse naturalmente com um agente que escuta, entende e age usando o contexto e as ferramentas da sua operação.</p>
        <div className="entryOrbButton" aria-label="Agente de voz">
          <span className="entryOrbCore" />
          <span className="entryOrbWave entryOrbWaveOne" />
          <span className="entryOrbWave entryOrbWaveTwo" />
        </div>
        <button type="button" className="entryCallButton" onClick={callAgent}>
          Chamar agente
        </button>
        <small>Experiência em português do Brasil</small>
      </section>
      <footer className="entryFooter">VOZ <span>·</span> CONTEXTO <span>·</span> AÇÃO</footer>
    </main>
  );
}
