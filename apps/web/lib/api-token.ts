import { createHmac } from "node:crypto";
import { Pool } from "pg";

const databaseUrl = process.env.DATABASE_URL?.replace("postgresql+asyncpg://", "postgresql://");
const pool = databaseUrl ? new Pool({ connectionString: databaseUrl }) : undefined;

function base64url(value: object) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export async function issueApiToken(userId: string) {
  if (!pool || !process.env.AUTH_SECRET) return null;
  const result = await pool.query<{ id: string; role: string }>(
    'SELECT tenant_id::text AS id, role FROM memberships WHERE "user_id"=$1 ORDER BY created_at',
    [userId],
  );
  if (result.rows.length === 0) return null;
  const now = Math.floor(Date.now() / 1000);
  const header = base64url({ alg: "HS256", typ: "JWT" });
  const payload = base64url({
    sub: userId,
    iss: process.env.JWT_ISSUER ?? "voiceos",
    aud: process.env.JWT_AUDIENCE ?? "voiceos-api",
    iat: now,
    exp: now + 5 * 60,
    tenants: result.rows,
  });
  const signature = createHmac("sha256", process.env.AUTH_SECRET).update(`${header}.${payload}`).digest("base64url");
  return { token: `${header}.${payload}.${signature}`, tenants: result.rows };
}
