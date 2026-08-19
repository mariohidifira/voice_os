import { createHmac } from "node:crypto";
import { NextResponse } from "next/server";
import { Pool } from "pg";
import { auth } from "../../../auth";

const databaseUrl = process.env.DATABASE_URL?.replace("postgresql+asyncpg://", "postgresql://");
const pool = databaseUrl ? new Pool({ connectionString: databaseUrl }) : undefined;

function base64url(value: object) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  if (!pool || !process.env.AUTH_SECRET) return NextResponse.json({ error: "not_configured" }, { status: 503 });

  const result = await pool.query<{ id: string; role: string }>(
    'SELECT tenant_id::text AS id, role FROM memberships WHERE "user_id"=$1 ORDER BY created_at',
    [session.user.id],
  );
  if (result.rows.length === 0) return NextResponse.json({ error: "no_membership" }, { status: 403 });

  const now = Math.floor(Date.now() / 1000);
  const header = base64url({ alg: "HS256", typ: "JWT" });
  const payload = base64url({
    sub: session.user.id,
    iss: process.env.JWT_ISSUER ?? "voiceos",
    aud: process.env.JWT_AUDIENCE ?? "voiceos-api",
    iat: now,
    exp: now + 5 * 60,
    tenants: result.rows,
  });
  const signature = createHmac("sha256", process.env.AUTH_SECRET).update(`${header}.${payload}`).digest("base64url");
  return NextResponse.json({ access_token: `${header}.${payload}.${signature}`, token_type: "Bearer", expires_in: 300, tenants: result.rows });
}
