import PostgresAdapter from "@auth/pg-adapter";
import NextAuth from "next-auth";
import { Pool } from "pg";
import authConfig from "./auth.config";

const databaseUrl = process.env.DATABASE_URL?.replace("postgresql+asyncpg://", "postgresql://");
const pool = databaseUrl ? new Pool({ connectionString: databaseUrl }) : undefined;
export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  secret: process.env.AUTH_SECRET,
  adapter: pool ? PostgresAdapter(pool) : undefined,
  session: { strategy: "jwt", maxAge: 60 * 60 },
  callbacks: {
    ...authConfig.callbacks,
    jwt({ token, user }) { if (user?.id) token.sub = user.id; return token; },
    session({ session, token }) { if (session.user && token.sub) session.user.id = token.sub; return session; },
  },
});
