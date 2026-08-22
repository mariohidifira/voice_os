import NextAuth from "next-auth";
import authConfig from "./auth.config";

export const { auth: middleware } = NextAuth({ ...authConfig, providers: [] });
export const config = { matcher: ["/app/:path*", "/admin/:path*", "/onboarding"] };
