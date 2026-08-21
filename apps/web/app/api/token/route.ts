import { NextResponse } from "next/server";
import { auth } from "../../../auth";
import { issueApiToken } from "../../../lib/api-token";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  const issued = await issueApiToken(session.user.id);
  if (!issued) return NextResponse.json({ error: "not_configured_or_no_membership" }, { status: 503 });
  return NextResponse.json({ access_token: issued.token, token_type: "Bearer", expires_in: 300, tenants: issued.tenants });
}
