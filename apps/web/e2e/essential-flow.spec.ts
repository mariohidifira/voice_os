import { expect, test } from "@playwright/test";

async function magicLogin(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
) {
  const previousEmail = await request.get("http://127.0.0.1:9000/email/last");
  const previousUrl = previousEmail.ok()
    ? (((await previousEmail.json()) as { url?: string }).url ?? "")
    : "";
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("owner@demo.voiceos.local");
  await page.getByRole("button", { name: "Enviar link mágico" }).click();

  let magicLink = "";
  await expect
    .poll(async () => {
      const response = await request.get("http://127.0.0.1:9000/email/last");
      if (!response.ok()) return "";
      const email = (await response.json()) as { to: string; url: string };
      magicLink = email.url;
      return email.to === "owner@demo.voiceos.local" &&
        email.url !== previousUrl
        ? email.to
        : "";
    })
    .toBe("owner@demo.voiceos.local");
  await page.goto(magicLink);
  await expect(page).toHaveURL(/\/app\/demo/);
  await expect(
    page.getByText("VoiceOS", { exact: false }).first(),
  ).toBeVisible();
}

test("criar agente, publicar, testar e ver chamada", async ({
  page,
  request,
}) => {
  await page.route("**/api/voiceos/voices", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          { id: "voice-e2e", name: "Ana E2E", labels: { language: "pt" } },
        ],
        configured: true,
      }),
    });
  });
  await page.route("**/api/voiceos/voices/voice-e2e/preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "audio/mpeg",
      body: "ID3preview",
    });
  });
  await magicLogin(page, request);

  await page.getByRole("button", { name: "Agentes", exact: true }).click();
  const agentName = `E2E ${Date.now()}`;
  await page.getByPlaceholder("Nome do agente").fill(agentName);
  await page.getByPlaceholder("Nome do agente").press("Enter");
  await expect(page.getByRole("heading", { name: agentName })).toBeVisible();
  await page.route("**/draft/improve-prompt", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        improved_prompt:
          "Você é {{ agent.name }} e atende testes E2E com respostas curtas e objetivas.",
      }),
    });
  });
  await page
    .getByLabel("Prompt do sistema")
    .fill(
      "Você é {{ agent.name }} e atende testes E2E com respostas objetivas.",
    );
  await expect(page.getByLabel("Variáveis detectadas")).toContainText(
    "{{ agent.name }}",
  );
  await expect(page.getByText(/\d+ \/ 6\.000 caracteres/)).toBeVisible();
  await page.getByRole("button", { name: "Melhorar com IA" }).click();
  await expect(page.getByLabel("Prompt do sistema")).toHaveValue(
    /respostas curtas e objetivas/,
  );
  await expect(page.getByRole("status")).toContainText("Sugestão gerada");
  await page.getByRole("button", { name: "Salvar rascunho" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Rascunho e ferramentas salvos",
  );
  await page.getByRole("tab", { name: "Voz" }).click();
  await expect(page.getByLabel("Idioma")).toBeVisible();
  await page.getByLabel("Voice ID").fill("voice-e2e");
  await page.getByRole("button", { name: "▶ Ouvir saudação" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Preview de voz sintetizado",
  );
  await expect(page.locator(".voicePreview audio")).toBeVisible();
  await page.getByRole("tab", { name: "Conversa" }).click();
  await expect(page.getByLabel("Duração máxima (s)")).toBeVisible();
  await page.getByRole("tab", { name: "Avançado" }).click();
  await page.getByLabel("Velocidade", { exact: true }).fill("1.1");
  await page.getByLabel("Keywords STT (vírgulas)").fill("VoiceOS, agendamento");
  await page
    .getByLabel("Frases de encerramento (separadas por |)")
    .fill("Obrigado pelo contato. | Até logo.");
  await page.getByLabel("Aplicar horário de funcionamento").check();
  await page
    .getByLabel("Mensagem fora do horário")
    .fill("Estamos fechados agora; posso registrar seu contato.");
  await page
    .getByRole("button", { name: "Salvar configuração avançada" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Configuração avançada salva",
  );
  await expect(
    page.getByLabel("Aplicar horário de funcionamento"),
  ).toBeChecked();
  await expect(page.getByLabel("Mensagem fora do horário")).toHaveValue(
    "Estamos fechados agora; posso registrar seu contato.",
  );
  await page.getByRole("tab", { name: "Conhecimento" }).click();
  await page
    .getByLabel("Base de conhecimento")
    .selectOption({ label: "Base Demo" });
  await page.getByLabel("Top K da busca").fill("7");
  await page.getByRole("button", { name: "Salvar rascunho" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Rascunho e ferramentas salvos",
  );
  await expect(page.getByLabel("Top K da busca")).toHaveValue("7");
  await page.getByRole("button", { name: "Testar busca" }).click();
  await expect(page.getByRole("heading", { name: "Base Demo" })).toBeVisible();
  await page.getByRole("button", { name: "Agentes", exact: true }).click();
  await page.getByRole("tab", { name: "Tools" }).click();
  await page.getByRole("button", { name: "Criar tool" }).click();
  await expect(
    page.getByRole("heading", { name: "Novo webhook" }),
  ).toBeVisible();
  const toolName = `webhook_e2e_${Date.now()}`;
  await page.getByLabel("Nome snake_case").fill(toolName);
  await page.getByLabel("Descrição").fill("Consulta o mock de teste E2E");
  await page.getByLabel("URL HTTPS").fill("http://127.0.0.1:9000/tool/ok");
  await page.getByLabel("Fala antes da execução").fill("Vou consultar agora.");
  await page.getByRole("button", { name: "Criar ferramenta" }).click();
  await expect(page.getByRole("status")).toContainText("Ferramenta criada");
  const toolRow = page.locator(".row.static").filter({ hasText: toolName });
  await expect(toolRow).toBeVisible();
  await toolRow.getByText("Testar", { exact: true }).first().click();
  await toolRow.getByRole("button", { name: "Testar" }).click();
  await expect(page.getByRole("status")).toContainText(/conclu/);
  await page.getByRole("button", { name: "Agentes", exact: true }).click();
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByRole("status")).toContainText("Versão publicada");

  await page.getByText(/Versões e rollback/).click();
  await expect(
    page.getByRole("button", { name: "Restaurar como rascunho" }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Restaurar como rascunho" })
    .first()
    .click();
  await expect(page.getByRole("status")).toContainText("Rollback aplicado");

  await page.getByRole("button", { name: "Testar" }).click();
  await expect(
    page.getByRole("dialog", { name: "Teste de voz" }),
  ).toBeVisible();
  const sessionResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/test-session") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Iniciar conversa" }).click();
  expect((await sessionResponse).status()).toBe(201);
  await page
    .getByRole("dialog", { name: "Teste de voz" })
    .getByRole("button", { name: "×" })
    .click();

  await page.getByRole("button", { name: /Configura/ }).click();
  const workspaceName = `Workspace E2E ${Date.now()}`;
  await page.getByLabel("Nome do workspace").fill(workspaceName);
  await page.getByLabel("Fuso horário").fill("America/Fortaleza");
  await page.getByLabel("Retenção das gravações (dias)").fill("180");
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Configurações gerais salvas",
  );
  await expect(page.getByLabel("Nome do workspace")).toHaveValue(workspaceName);
  const secretName = `secret_e2e_${Date.now()}`;
  await page.getByPlaceholder("crm_api_key").fill(secretName);
  await page.getByLabel("Valor secreto").fill("e2e-secret-value");
  await page.getByRole("button", { name: "Salvar secret" }).click();
  await expect(page.getByRole("status")).toContainText("Secret criptografado");
  const secretRow = page.locator(".row.static").filter({ hasText: secretName });
  await expect(secretRow).toBeVisible();
  await secretRow.getByRole("button", { name: "Remover" }).click();
  await expect(page.getByRole("status")).toContainText("Secret removido");

  await page.getByRole("button", { name: "Membros", exact: true }).click();
  const ownerRow = page
    .locator(".row.static")
    .filter({ hasText: "owner@demo.voiceos.local" });
  await expect(
    ownerRow.getByLabel("Papel de owner@demo.voiceos.local"),
  ).toBeDisabled();
  await expect(ownerRow.getByRole("button", { name: "Remover" })).toBeDisabled();

  await page.getByRole("button", { name: "Chamadas", exact: true }).click();
  await expect(
    page
      .getByText("test_session", { exact: false })
      .or(page.getByText("cancelled", { exact: false }))
      .first(),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "completed · web 120s · Chamada demo 1",
      exact: true,
    })
    .click();
  const synchronizedTurn = page.getByRole("button", {
    name: /Ir para 0 segundos: Olá, quero agendar/,
  });
  await expect(synchronizedTurn).toBeVisible();
  await synchronizedTurn.click();
});

test("onboarding cria tenant, agente por template e abre teste", async ({
  page,
  request,
}) => {
  await magicLogin(page, request);
  await page.goto("/onboarding");
  const company = `Operação E2E ${Date.now()}`;
  await page.getByPlaceholder("Clínica Exemplo").fill(company);
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Template").selectOption("scheduling");
  await page.getByPlaceholder("Ana").fill("Agenda E2E");
  await page.getByRole("button", { name: "Criar e testar" }).click();
  await expect(page).toHaveURL(/\/app\/operacao-e2e-/);
  await expect(
    page.getByRole("dialog", { name: "Teste de voz" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Agenda E2E draft/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Recepcionista active/ }),
  ).toHaveCount(0);
});
