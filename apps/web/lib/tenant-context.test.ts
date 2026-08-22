import { describe, expect, it } from "vitest";
import { selectTenant, tenantSlugFromReferer } from "./tenant-context";

const memberships = [
  { id: "tenant-demo", slug: "demo" },
  { id: "tenant-clinic", slug: "clinica-sao-jose" },
];

describe("tenant request context", () => {
  it("extracts the workspace slug from dashboard URLs", () => {
    expect(tenantSlugFromReferer("https://voice.example/app/clinica-sao-jose?tab=agents")).toBe("clinica-sao-jose");
  });

  it("selects the membership matching the active dashboard", () => {
    expect(selectTenant(memberships, "https://voice.example/app/clinica-sao-jose")).toEqual(memberships[1]);
  });

  it("falls back deterministically when no dashboard context exists", () => {
    expect(selectTenant(memberships, "https://voice.example/onboarding")).toEqual(memberships[0]);
    expect(tenantSlugFromReferer("https://voice.example/app/%E0%A4%A")).toBeUndefined();
  });
});
