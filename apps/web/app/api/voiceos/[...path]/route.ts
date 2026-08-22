import { NextRequest, NextResponse } from "next/server";
import { auth } from "../../../../auth";
import { issueApiToken } from "../../../../lib/api-token";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const session = await auth();
  if (!session?.user?.id) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  const issued = await issueApiToken(session.user.id);
  if (!issued) return NextResponse.json({ error: "not_configured_or_no_membership" }, { status: 503 });
  const { path } = await context.params;
  const apiBase = process.env.API_INTERNAL_URL ?? "http://api:8000";
  const target = new URL(`/v1/${path.join("/")}${request.nextUrl.search}`, apiBase);
  const headers = new Headers(request.headers);
  const referer = request.headers.get("referer") ?? "";
  const tenantSlug = /\/app\/([^/?#]+)/.exec(referer)?.[1];
  const selectedTenant = issued.tenants.find((tenant) => tenant.slug === tenantSlug) ?? issued.tenants[0];
  headers.set("authorization", `Bearer ${issued.token}`);
  headers.set("x-tenant-id", headers.get("x-tenant-id") ?? selectedTenant.id);
  headers.delete("host");
  headers.delete("cookie");
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });
  return new NextResponse(response.body, { status: response.status, headers: response.headers });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
