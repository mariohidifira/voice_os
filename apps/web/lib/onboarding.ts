export function slugifyWorkspace(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48) || "workspace";
}

export function availableWorkspaceSlug(name: string, occupied: Iterable<string>) {
  const baseSlug = slugifyWorkspace(name);
  const used = new Set(occupied);
  let slug = baseSlug;
  for (let suffix = 2; used.has(slug); suffix += 1) slug = `${baseSlug}-${suffix}`;
  return slug;
}
