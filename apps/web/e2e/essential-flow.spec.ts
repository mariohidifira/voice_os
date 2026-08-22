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
  await magicLogin(page, request);

  await page.getByRole("button", { name: "Agentes", exact: true }).click();
  const agentName = `E2E ${Date.now()}`;
  await page.getByPlaceholder("Nome do agente").fill(agentName);
  await page.getByPlaceholder("Nome do agente").press("Enter");
  await expect(page.getByRole("heading", { name: agentName })).toBeVisible();
  await page
    .getByLabel("Prompt do sistema")
    .fill("Você atende testes E2E com respostas objetivas.");
  await page.getByRole("button", { name: "Salvar rascunho" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Rascunho e ferramentas salvos",
  );
  await page.getByRole("tab", { name: "Voz" }).click();
  await expect(page.getByLabel("Idioma")).toBeVisible();
  await page.getByRole("tab", { name: "Conversa" }).click();
  await expect(page.getByLabel("Duração máxima (s)")).toBeVisible();
  await page.getByRole("tab", { name: "Avançado" }).click();
  await page.getByLabel("Velocidade").fill("1.1");
  await page.getByLabel("Keywords STT (vírgulas)").fill("VoiceOS, agendamento");
  await page
    .getByRole("button", { name: "Salvar configuração avançada" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Configuração avançada salva",
  );
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByRole("status")).toContainText("Versão publicada");

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
