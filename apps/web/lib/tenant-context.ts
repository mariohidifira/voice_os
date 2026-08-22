export type TenantMembership = { id: string; slug: string };

export function tenantSlugFromReferer(referer: string) {
  const encoded = /\/app\/([^/?#]+)/.exec(referer)?.[1];
  if (!encoded) return undefined;
  try {
    return decodeURIComponent(encoded);
  } catch {
    return undefined;
  }
}

export function selectTenant(memberships: TenantMembership[], referer: string) {
  const slug = tenantSlugFromReferer(referer);
  return memberships.find((tenant) => tenant.slug === slug) ?? memberships[0];
}
