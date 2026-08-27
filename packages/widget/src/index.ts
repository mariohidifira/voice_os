export type VoiceOSTheme = "light" | "dark" | "system";
export type VoiceOSPosition = "bottom-right" | "bottom-left";
export type VoiceOSEventName = "voiceos:start" | "voiceos:end";
export type VoiceOSWidgetState =
  | "idle"
  | "connecting"
  | "connected"
  | "ended"
  | "error";

export interface VoiceOSEndUser {
  external_id?: string;
  phone?: string;
  email?: string;
  name?: string;
  metadata?: Record<string, unknown>;
}

export interface VoiceOSOptions {
  agentId: string;
  publicKey: string;
  apiUrl: string;
  theme?: VoiceOSTheme;
  position?: VoiceOSPosition;
  buttonLabel?: string;
  zIndex?: number;
  variables?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  endUser?: VoiceOSEndUser;
  livekitModuleUrl?: string;
  onStart?: () => void;
  onEnd?: () => void;
}

type Session = {
  session_id: string;
  call_id: string;
  livekit_url: string;
  token: string;
};

type RemoteTrack = {
  kind: string;
  attach(): HTMLElement;
  detach(): HTMLElement[];
};

type RemoteParticipant = { audioLevel: number };
type LocalParticipant = {
  audioLevel: number;
  setMicrophoneEnabled(
    enabled: boolean,
    options?: {
      echoCancellation?: boolean;
      noiseSuppression?: boolean;
      autoGainControl?: boolean;
    },
  ): Promise<void>;
};

type Room = {
  on(event: string, listener: (...args: any[]) => void): void;
  connect(url: string, token: string, options?: { autoSubscribe?: boolean }): Promise<void>;
  disconnect(): Promise<void>;
  startAudio(): Promise<void>;
  remoteParticipants: Map<string, RemoteParticipant>;
  localParticipant: LocalParticipant;
};

type LiveKitModule = {
  Room: new (options?: { adaptiveStream?: boolean; dynacast?: boolean }) => Room;
  RoomEvent: {
    TrackSubscribed: string;
    TrackUnsubscribed: string;
    Disconnected: string;
  };
  Track: { Kind: { Audio: string } };
};

const DEFAULTS = {
  theme: "system" as VoiceOSTheme,
  position: "bottom-right" as VoiceOSPosition,
  buttonLabel: "Falar agora",
  zIndex: 9999,
  variables: {} as Record<string, unknown>,
  metadata: {} as Record<string, unknown>,
  livekitModuleUrl:
    "https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.esm.mjs",
};

export class VoiceOSWidget {
  private button: HTMLButtonElement;

  private overlay: HTMLDivElement;

  private card: HTMLDivElement;

  private title: HTMLHeadingElement;

  private status: HTMLParagraphElement;

  private actions: HTMLDivElement;

  private audio: HTMLDivElement;

  private footnote: HTMLParagraphElement;

  private mounted = false;

  private opened = false;

  private muted = false;

  private state: VoiceOSWidgetState = "idle";

  private notice = "Clique para iniciar a conversa por voz.";

  private session: Session | null = null;

  private room: Room | null = null;

  private meterId: number | null = null;

  private attempt = 0;

  private options: Required<
    Pick<
      VoiceOSOptions,
      | "agentId"
      | "publicKey"
      | "apiUrl"
      | "theme"
      | "position"
      | "buttonLabel"
      | "zIndex"
      | "variables"
      | "metadata"
      | "livekitModuleUrl"
    >
  > &
    Pick<VoiceOSOptions, "endUser" | "onStart" | "onEnd">;

  constructor(options: VoiceOSOptions) {
    this.options = {
      ...DEFAULTS,
      ...options,
      variables: { ...DEFAULTS.variables, ...(options.variables ?? {}) },
      metadata: { ...DEFAULTS.metadata, ...(options.metadata ?? {}) },
    };
    this.button = document.createElement("button");
    this.overlay = document.createElement("div");
    this.card = document.createElement("div");
    this.title = document.createElement("h2");
    this.status = document.createElement("p");
    this.actions = document.createElement("div");
    this.audio = document.createElement("div");
    this.footnote = document.createElement("p");

    this.button.type = "button";
    this.button.setAttribute("aria-label", "Abrir widget de voz");
    this.button.addEventListener("click", () => {
      if (this.opened) {
        this.close();
      } else {
        this.open();
      }
    });

    this.overlay.setAttribute("aria-hidden", "true");
    this.overlay.addEventListener("click", (event) => {
      if (event.target === this.overlay) {
        this.close();
      }
    });

    this.card.setAttribute("role", "dialog");
    this.card.setAttribute("aria-modal", "true");
    this.card.setAttribute("aria-label", "VoiceOS widget");

    this.audio.setAttribute("aria-hidden", "true");
    this.render();
  }

  mount(root: HTMLElement = document.body): void {
    if (this.mounted) {
      return;
    }
    this.overlay.appendChild(this.card);
    root.appendChild(this.button);
    root.appendChild(this.overlay);
    this.mounted = true;
    this.render();
  }

  unmount(): void {
    if (!this.mounted) {
      return;
    }
    this.attempt += 1;
    void this.shutdown(false);
    this.overlay.remove();
    this.button.remove();
    this.mounted = false;
  }

  open(): void {
    if (this.opened) {
      return;
    }
    this.opened = true;
    this.state = "connecting";
    this.notice = "Conectando à sala segura...";
    this.render();
    const attempt = ++this.attempt;
    void this.startSession(attempt);
  }

  close(): void {
    if (!this.opened && this.state === "idle") {
      return;
    }
    this.attempt += 1;
    void this.shutdown(true);
  }

  update(partial: Partial<VoiceOSOptions>): void {
    this.options = {
      ...this.options,
      ...partial,
      variables: { ...this.options.variables, ...(partial.variables ?? {}) },
      metadata: { ...this.options.metadata, ...(partial.metadata ?? {}) },
    };
    this.render();
  }

  private async startSession(attempt: number): Promise<void> {
    try {
      const response = await fetch(this.options.apiUrl, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": this.options.publicKey,
        },
        body: JSON.stringify({
          agent_id: this.options.agentId,
          variables: this.options.variables,
          metadata: { ...this.options.metadata, source: "embedded_widget" },
          end_user: this.options.endUser,
        }),
      });
      if (!response.ok) {
        throw new Error(await readError(response));
      }
      const session = (await response.json()) as Session;
      if (attempt !== this.attempt) {
        return;
      }
      this.session = session;

      const livekit = await loadLiveKitModule(this.options.livekitModuleUrl);
      if (attempt !== this.attempt) {
        return;
      }
      const room = new livekit.Room({ adaptiveStream: true, dynacast: true });
      this.room = room;
      room.on(livekit.RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === livekit.Track.Kind.Audio) {
          this.audio.appendChild(track.attach());
        }
      });
      room.on(livekit.RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
        track.detach().forEach((element) => element.remove());
      });
      room.on(livekit.RoomEvent.Disconnected, () => {
        this.stopMeter();
        this.room = null;
        this.session = null;
        if (this.opened) {
          this.state = "ended";
          this.notice = "Chamada encerrada.";
          this.render();
        }
      });

      await room.connect(session.livekit_url, session.token, { autoSubscribe: true });
      if (attempt !== this.attempt) {
        await room.disconnect();
        return;
      }
      await room.startAudio();
      await room.localParticipant.setMicrophoneEnabled(true, {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      });
      if (attempt !== this.attempt) {
        await room.disconnect();
        return;
      }
      this.state = "connected";
      this.muted = false;
      this.notice = "Conectado. Pode falar.";
      this.startMeter();
      this.options.onStart?.();
      emitWidgetEvent("voiceos:start", this.options.agentId);
      this.render();
    } catch (error) {
      if (attempt !== this.attempt) {
        return;
      }
      this.state = "error";
      this.notice = error instanceof Error ? error.message : "Não foi possível conectar.";
      this.render();
    }
  }

  private async shutdown(notify: boolean): Promise<void> {
    const session = this.session;
    const room = this.room;
    this.stopMeter();
    this.muted = false;
    this.room = null;
    this.session = null;
    this.audio.replaceChildren();

    try {
      await room?.localParticipant.setMicrophoneEnabled(false);
    } catch {}
    try {
      await room?.disconnect();
    } catch {}
    if (session) {
      try {
        await fetch(`${this.options.apiUrl}/${session.session_id}`, {
          method: "DELETE",
          headers: {
            "x-api-key": this.options.publicKey,
          },
        });
      } catch {}
    }

    this.opened = false;
    this.state = "idle";
    this.notice = "Clique para iniciar a conversa por voz.";
    if (notify) {
      this.options.onEnd?.();
      emitWidgetEvent("voiceos:end", this.options.agentId);
    }
    this.render();
  }

  private async toggleMute(): Promise<void> {
    const room = this.room;
    if (!room) {
      return;
    }
    await room.localParticipant.setMicrophoneEnabled(this.muted);
    this.muted = !this.muted;
    this.notice = this.muted ? "Microfone pausado." : "Microfone ativo.";
    this.render();
  }

  private retry(): void {
    this.attempt += 1;
    void this.shutdown(false).finally(() => this.open());
  }

  private startMeter(): void {
    this.stopMeter();
    const room = this.room;
    if (!room) {
      return;
    }
    this.meterId = window.setInterval(() => {
      const remote = Math.max(
        0,
        ...Array.from(room.remoteParticipants.values()).map((participant) => participant.audioLevel),
      );
      const level = Math.max(room.localParticipant.audioLevel, remote, 0.05);
      this.card.style.setProperty("--voiceos-level", String(level));
    }, 120);
  }

  private stopMeter(): void {
    if (this.meterId !== null) {
      window.clearInterval(this.meterId);
      this.meterId = null;
    }
    this.card.style.setProperty("--voiceos-level", "0.05");
  }

  private render(): void {
    const theme = resolveTheme(this.options.theme);
    const palette =
      theme === "dark"
        ? {
            panel: "rgba(5, 35, 27, 0.96)",
            overlay: "rgba(0, 0, 0, 0.48)",
            accent: "#78e6c0",
            foreground: "#f5fff9",
            muted: "#9cc9bb",
            border: "#1d5b49",
          }
        : {
            panel: "rgba(255, 255, 255, 0.98)",
            overlay: "rgba(5, 35, 27, 0.24)",
            accent: "#0f8f68",
            foreground: "#05231b",
            muted: "#42695d",
            border: "#9ad8c4",
          };
    const positionStyles =
      this.options.position === "bottom-left"
        ? { left: "24px", right: "auto" }
        : { right: "24px", left: "auto" };

    this.button.textContent =
      this.state === "connected" && this.opened
        ? `Encerrar • ${this.options.buttonLabel}`
        : this.options.buttonLabel;
    this.button.dataset.agentId = this.options.agentId;
    this.button.dataset.apiUrl = this.options.apiUrl;
    this.button.dataset.position = this.options.position;
    this.button.dataset.state = this.state;
    Object.assign(this.button.style, {
      position: "fixed",
      bottom: "24px",
      ...positionStyles,
      border: `1px solid ${palette.border}`,
      borderRadius: "999px",
      padding: "14px 20px",
      background: theme === "dark" ? "#05231b" : "#78e6c0",
      color: theme === "dark" ? "#f5fff9" : "#05231b",
      fontWeight: "700",
      cursor: "pointer",
      boxShadow: "0 12px 32px rgba(0,0,0,0.18)",
      fontFamily:
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      zIndex: String(this.options.zIndex),
    } satisfies Partial<CSSStyleDeclaration>);

    Object.assign(this.overlay.style, {
      position: "fixed",
      inset: "0",
      display: this.opened ? "grid" : "none",
      placeItems: "end",
      padding: "24px",
      background: palette.overlay,
      zIndex: String(this.options.zIndex + 1),
    } satisfies Partial<CSSStyleDeclaration>);

    Object.assign(this.card.style, {
      "--voiceos-level": "0.05",
      width: "min(420px, calc(100vw - 32px))",
      borderRadius: "24px",
      border: `1px solid ${palette.border}`,
      background: palette.panel,
      color: palette.foreground,
      boxShadow: "0 24px 80px rgba(0,0,0,0.28)",
      padding: "24px",
      fontFamily:
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      justifySelf: this.options.position === "bottom-left" ? "start" : "end",
    } satisfies Partial<CSSStyleDeclaration>);

    this.title.textContent = "VoiceOS Widget";
    Object.assign(this.title.style, {
      margin: "0 0 8px",
      fontSize: "1.125rem",
    } satisfies Partial<CSSStyleDeclaration>);

    this.status.textContent = this.notice;
    Object.assign(this.status.style, {
      margin: "0 0 16px",
      color: palette.muted,
      lineHeight: "1.5",
    } satisfies Partial<CSSStyleDeclaration>);

    Object.assign(this.audio.style, {
      width: "100%",
      minHeight: "8px",
    } satisfies Partial<CSSStyleDeclaration>);

    this.footnote.textContent =
      this.state === "connected"
        ? "Microfone ativo. Use fones para melhor cancelamento de eco."
        : "O navegador solicitará permissão de microfone quando a chamada iniciar.";
    Object.assign(this.footnote.style, {
      margin: "16px 0 0",
      fontSize: "0.875rem",
      color: palette.muted,
    } satisfies Partial<CSSStyleDeclaration>);

    Object.assign(this.actions.style, {
      display: "flex",
      gap: "12px",
      flexWrap: "wrap",
      marginTop: "16px",
    } satisfies Partial<CSSStyleDeclaration>);
    this.actions.replaceChildren(...this.buildActionButtons(palette));

    const header = document.createElement("div");
    Object.assign(header.style, {
      display: "flex",
      alignItems: "start",
      justifyContent: "space-between",
      gap: "16px",
    } satisfies Partial<CSSStyleDeclaration>);

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.textContent = "×";
    closeButton.setAttribute("aria-label", "Fechar widget");
    closeButton.addEventListener("click", () => this.close());
    Object.assign(closeButton.style, {
      border: `1px solid ${palette.border}`,
      background: "transparent",
      color: palette.foreground,
      borderRadius: "999px",
      width: "36px",
      height: "36px",
      cursor: "pointer",
      fontSize: "1.25rem",
    } satisfies Partial<CSSStyleDeclaration>);

    const heading = document.createElement("div");
    const eyebrow = document.createElement("div");
    eyebrow.textContent = this.state === "connected" ? "WebRTC ativo" : "widget embutível";
    Object.assign(eyebrow.style, {
      textTransform: "uppercase",
      letterSpacing: "0.08em",
      fontSize: "0.75rem",
      color: palette.muted,
      marginBottom: "6px",
    } satisfies Partial<CSSStyleDeclaration>);
    heading.appendChild(eyebrow);
    heading.appendChild(this.title);
    header.appendChild(heading);
    header.appendChild(closeButton);

    const orb = document.createElement("div");
    Object.assign(orb.style, {
      width: "88px",
      height: "88px",
      margin: "8px 0 16px",
      borderRadius: "999px",
      background: `radial-gradient(circle, ${palette.accent} 0%, transparent 68%)`,
      transform: `scale(calc(0.92 + var(--voiceos-level)))`,
      transition: "transform 120ms ease-out",
    } satisfies Partial<CSSStyleDeclaration>);

    this.card.replaceChildren(header, orb, this.status, this.audio, this.actions, this.footnote);
  }

  private buildActionButtons(
    palette: Record<"accent" | "foreground" | "border", string>,
  ): HTMLButtonElement[] {
    if (this.state === "connecting") {
      return [makeButton("Conectando...", () => undefined, palette, true)];
    }
    if (this.state === "connected") {
      return [
        makeButton(
          this.muted ? "Ativar microfone" : "Silenciar",
          () => {
            void this.toggleMute();
          },
          palette,
        ),
        makeButton("Encerrar", () => this.close(), palette),
      ];
    }
    if (this.state === "error" || this.state === "ended") {
      return [
        makeButton("Tentar novamente", () => this.retry(), palette),
        makeButton("Fechar", () => this.close(), palette),
      ];
    }
    return [];
  }
}

function makeButton(
  label: string,
  onClick: () => void,
  palette: Record<"accent" | "foreground" | "border", string>,
  disabled = false,
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  Object.assign(button.style, {
    border: `1px solid ${palette.border}`,
    borderRadius: "999px",
    padding: "12px 16px",
    background: disabled ? "transparent" : palette.accent,
    color: disabled ? palette.foreground : "#05231b",
    cursor: disabled ? "default" : "pointer",
    fontWeight: "700",
  } satisfies Partial<CSSStyleDeclaration>);
  return button;
}

function resolveTheme(theme: VoiceOSTheme): "light" | "dark" {
  if (theme === "system") {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return theme;
}

function emitWidgetEvent(name: VoiceOSEventName, agentId: string): void {
  window.dispatchEvent(new CustomEvent(name, { detail: { agentId } }));
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: { message?: string } | string;
      message?: string;
    };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    return payload.detail?.message || payload.message || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

async function loadLiveKitModule(moduleUrl: string): Promise<LiveKitModule> {
  return (await import(/* @vite-ignore */ moduleUrl)) as LiveKitModule;
}

function bootstrapFromScriptTag(): void {
  if (typeof document === "undefined") {
    return;
  }
  const script = document.currentScript;
  if (!(script instanceof HTMLScriptElement)) {
    return;
  }
  const agentId = script.dataset.agentId;
  const publicKey = script.dataset.key;
  const apiUrl = script.dataset.apiUrl;
  if (!agentId || !publicKey || !apiUrl) {
    return;
  }
  new VoiceOSWidget({
    agentId,
    publicKey,
    apiUrl,
    buttonLabel: script.dataset.buttonLabel || undefined,
    theme: (script.dataset.theme as VoiceOSTheme | undefined) || undefined,
    position: (script.dataset.position as VoiceOSPosition | undefined) || undefined,
    livekitModuleUrl: script.dataset.livekitModuleUrl || undefined,
  }).mount();
}

if (typeof window !== "undefined") {
  (window as Window & { VoiceOSWidget?: typeof VoiceOSWidget }).VoiceOSWidget = VoiceOSWidget;
  bootstrapFromScriptTag();
}
