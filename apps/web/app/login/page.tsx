import { signIn } from "../../auth";

export default function Login() {
  async function emailLogin(formData: FormData) {
    "use server";
    await signIn("resend", { email: String(formData.get("email")), redirectTo: "/app/demo" });
  }
  async function googleLogin() {
    "use server";
    await signIn("google", { redirectTo: "/app/demo" });
  }
  return <main style={{ maxWidth: 460, margin: "10vh auto" }}><div className="eyebrow">VoiceOS</div><h1>Entre na sua operação</h1><p className="muted">Receba um link seguro por e-mail ou continue com Google.</p><form action={emailLogin} className="card"><label htmlFor="email">E-mail</label><input id="email" name="email" type="email" required style={{ width: "100%", margin: "8px 0 16px", padding: 12, borderRadius: 8, border: "1px solid var(--line)", background: "var(--bg)", color: "white" }} /><button type="submit" style={{ width: "100%" }}>Enviar link mágico</button></form><form action={googleLogin} style={{ marginTop: 12 }}><button type="submit" style={{ width: "100%", background: "var(--panel)", color: "var(--text)", border: "1px solid var(--line)" }}>Continuar com Google</button></form></main>;
}

