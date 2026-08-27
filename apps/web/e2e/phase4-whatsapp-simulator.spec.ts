import { expect, test } from "@playwright/test";

async function magicLogin(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
) {
  const previousEmail = await request.get("http://localhost:9000/email/last");
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
}

test("configura WhatsApp, roda simulador e faz handoff humano no live", async ({
  page,
  request,
}) => {
  await magicLogin(page, request);
  await page.goto("/app/demo");

  const phoneNumberId = `phone-e2e-${Date.now()}`;
  const businessAccountId = `waba-e2e-${Date.now()}`;

  await page.getByRole("button", { name: /Configura/ }).click();
  await expect(page.getByRole("heading", { name: "WhatsApp Cloud API" })).toBeVisible();
  await page.getByLabel("Phone Number ID").fill(phoneNumberId);
  await page.getByLabel("Business Account ID").fill(businessAccountId);
  await page.getByLabel("Agente padrao").selectOption({ label: "Recepcionista" });
  await page.getByLabel("Access token").fill("token-e2e-whatsapp-abcdefgh");
  await page.getByRole("button", { name: "Salvar WhatsApp" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Integração do WhatsApp conectada.",
  );
  await expect(page.getByText(new RegExp(`Conectado em ${phoneNumberId}`))).toBeVisible();

  await page.getByRole("button", { name: "Simulador", exact: true }).click();
  const simulatorForm = page
    .locator("form.formGrid")
    .filter({ has: page.getByRole("button", { name: "Rodar simulador" }) });
  await simulatorForm
    .getByRole("combobox", { name: "Agente" })
    .selectOption({ label: "Recepcionista" });
  await page
    .getByLabel("Persona")
    .fill("Paciente recorrente com dúvidas de agenda e retorno.");
  await page
    .getByLabel("Objetivo")
    .fill("Verificar se o agente conduz a conversa com clareza e contexto.");
  await page.getByLabel("Quantidade de conversas").fill("20");
  await page.getByRole("button", { name: "Rodar simulador" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Simulação concluída e relatório carregado.",
  );
  await expect(page.getByText("YAML exportado")).toBeVisible();
  await expect(page.getByText(/channel: whatsapp/).first()).toBeVisible();
  await expect(page.getByText(/"conversation_count": 20/).first()).toBeVisible();

  const webhookPayload = {
    entry: [
      {
        changes: [
          {
            value: {
              metadata: { phone_number_id: phoneNumberId },
              messages: [
                {
                  id: `wamid-e2e-${Date.now()}`,
                  from: "+5511555551234",
                  type: "text",
                  text: { body: "Preciso de ajuda humana no WhatsApp" },
                },
              ],
            },
          },
        ],
      },
    ],
  };
  const webhookResponse = await request.post("http://localhost:8005/webhooks/whatsapp", {
    data: webhookPayload,
  });
  expect(webhookResponse.ok()).toBeTruthy();

  await page.reload();
  await page.getByRole("button", { name: "Ao vivo", exact: true }).click();
  const activeWhatsappRow = page
    .locator(".row")
    .filter({ hasText: "whatsapp" })
    .filter({ hasText: "in_progress" })
    .first();
  await expect(activeWhatsappRow).toBeVisible();
  await activeWhatsappRow.getByRole("button", { name: "Acompanhar" }).click();
  await expect(page.getByRole("heading", { name: "Handoff humano por texto" })).toBeVisible();
  await page
    .getByPlaceholder("Digite a resposta que deve seguir para o WhatsApp")
    .fill("Operador E2E assumiu a conversa.");
  await page.getByRole("button", { name: "Enviar no WhatsApp" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Mensagem do operador enviada no WhatsApp.",
  );
  await expect(
    page.getByPlaceholder("Digite a resposta que deve seguir para o WhatsApp"),
  ).toHaveValue("");
});
