import { describe, expect, it } from "vitest";
import { availableWorkspaceSlug, slugifyWorkspace } from "./onboarding";

describe("workspace slugs", () => {
  it("normalizes accents, punctuation and casing", () => {
    expect(slugifyWorkspace("  Clínica São José & Filhos  ")).toBe("clinica-sao-jose-filhos");
  });

  it("uses a safe fallback and limits the base length", () => {
    expect(slugifyWorkspace("!!!")).toBe("workspace");
    expect(slugifyWorkspace("a".repeat(60))).toHaveLength(48);
  });

  it("selects the first unoccupied numeric suffix", () => {
    expect(availableWorkspaceSlug("Minha Operação", ["minha-operacao", "minha-operacao-2"])).toBe("minha-operacao-3");
  });
});
