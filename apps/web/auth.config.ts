import type { NextAuthConfig } from "next-auth";
import type { Provider } from "next-auth/providers";
import Google from "next-auth/providers/google";
import Resend from "next-auth/providers/resend";

const emailProvider = Resend({
  apiKey: process.env.RESEND_API_KEY ?? "dev",
  from: process.env.AUTH_EMAIL_FROM ?? "VoiceOS <login@voiceos.example>",
  maxAge: 15 * 60,
});
if (process.env.APP_ENV === "dev") {
  emailProvider.sendVerificationRequest = async ({ identifier, url }) => {
    const response = await fetch(process.env.EMAIL_MOCK_URL ?? "http://localhost:9000/email", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ to: identifier, url }),
    });
    if (!response.ok) throw new Error(`Development email mock returned ${response.status}`);
  };
}

const providers: Provider[] = [emailProvider];
if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(Google({ clientId: process.env.GOOGLE_CLIENT_ID, clientSecret: process.env.GOOGLE_CLIENT_SECRET }));
}
const secureCookies = (process.env.AUTH_URL ?? "").startsWith("https://");

export default {
  secret: process.env.AUTH_SECRET,
  providers,
  pages: { signIn: "/login", verifyRequest: "/login?sent=1" },
  cookies: {
    sessionToken: {
      name: secureCookies ? "__Secure-voiceos.session-token" : "voiceos.session-token",
      options: { httpOnly: true, sameSite: "lax", path: "/", secure: secureCookies },
    },
  },
  callbacks: {
    authorized({ auth }) { return Boolean(auth?.user); },
  },
} satisfies NextAuthConfig;
