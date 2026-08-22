import { describe, expect, it } from "vitest";
import { extractPromptVariables } from "./prompt-utils";

describe("extractPromptVariables", () => {
  it("detects and deduplicates Jinja variables", () => {
    expect(
      extractPromptVariables(
        "{{ agent.name }} atende {{ var.nome }}. Olá {{ agent.name }}",
      ),
    ).toEqual(["agent.name", "var.nome"]);
  });

  it("removes filters from the detected variable name", () => {
    expect(extractPromptVariables('{{ var.horario | default("9h") }}')).toEqual(
      ["var.horario"],
    );
  });
});
