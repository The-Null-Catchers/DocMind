import { expect, test, type APIResponse } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";

test.use({ video: "on" });

const fixture = (name: string) => `e2e/fixtures/${name}`;

async function json<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), `${response.url()} returned HTTP ${response.status()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

test("synthetic portfolio demo: Arabic scan, citations, table and JSON", async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const api = process.env.API_BASE_URL ?? "http://localhost:8000/api/v1";
  const email = `portfolio-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";
  const { access_token } = await json<{ access_token: string }>(await request.post(`${api}/auth/register`, {
    data: {
      email,
      password,
      display_name: "Portfolio demo",
      locale: "en",
    },
  }));
  const headers = { authorization: `Bearer ${access_token}` };
  const createWorkspace = async (name: string) =>
    json<{ id: string }>(await request.post(`${api}/workspaces`, { headers, data: { name, kind: "personal" } }));
  const primary = await createWorkspace("Synthetic project library");
  const empty = await createWorkspace("Empty project library");

  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/app(?:\/)?$/);

  const waitUntilReady = async (id: string) => {
    await expect.poll(async () => (
      await json<{ status: string }>(await request.get(`${api}/documents/${id}`, { headers }))
    ).status, { timeout: 60_000, intervals: [250, 1000, 2000] }).toBe("ready");
  };
  const upload = async (name: string, mimeType: string) => {
    const doc = await json<{ id: string }>(await request.post(`${api}/documents/upload`, {
      headers,
      multipart: {
        workspace_id: primary.id,
        file: { name, mimeType, buffer: await readFile(fixture(name)) },
      },
    }));
    await waitUntilReady(doc.id);
    return doc.id;
  };

  await page.goto("/app/documents");
  await expect(page.getByRole("heading", { name: "Documents", exact: true, level: 1 })).toBeVisible();
  const selector = page.getByRole("combobox", { name: "Active workspace", exact: true }).first();
  await selector.selectOption(primary.id);
  await expect(selector).toHaveValue(primary.id);
  const pendingUpload = page.waitForResponse((response) =>
    response.url() === `${api}/documents/upload` && response.request().method() === "POST");
  await page.locator('input[type="file"]').setInputFiles(fixture("atlas-scan.pdf"));
  const uploaded = await pendingUpload;
  expect(uploaded.status()).toBe(202);
  const { id: scanId } = await uploaded.json() as { id: string };
  await waitUntilReady(scanId);
  const ocrPage = await json<{ text: string; ocr_used: boolean }>(
    await request.get(`${api}/documents/${scanId}/pages/2`, { headers }),
  );
  expect(ocrPage.ocr_used).toBe(true);
  expect(ocrPage.text).toMatch(/[\u0621-\u064A]{3,}/);
  expect(ocrPage.text).toContain("42000");

  await page.getByText("atlas-scan", { exact: true }).click();
  const chat = page.getByPlaceholder("Ask about this document…");
  await chat.fill("ما الميزانية المعتمدة لمشروع ATLAS؟");
  await page.getByRole("button", { name: "Send question" }).click();
  const citation = page.getByRole("button", { name: /Source 1.*Page 2/ });
  await expect(citation).toContainText("42000");
  await citation.click();
  await expect(page).toHaveURL(/[?&]page=2(?:&|$)/);
  await expect(page.locator('.react-pdf__Page[data-page-number="2"] canvas')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("portfolio-arabic-citation.png") });

  const tableId = await upload("project-budgets.csv", "text/csv");
  await page.goto(`/app/documents/${tableId}`);
  await expect(page.getByRole("row").filter({ hasText: "Atlas" })).toContainText("42000");
  await expect(page.getByRole("row").filter({ hasText: "Cedar" })).toContainText("30000");
  await page.screenshot({ path: testInfo.outputPath("portfolio-budget-table.png") });

  const recordId = await upload("atlas-record.txt", "text/plain");
  const extraction = await json<{ data: unknown; sources: unknown[] }>(
    await request.post(`${api}/extract`, {
      headers,
      data: {
        workspace_id: primary.id,
        document_ids: [recordId],
        schema_definition: {
          type: "object",
          properties: { project: { type: "string" }, approved_budget_ils: { type: "integer" } },
        },
      },
    }),
  );
  expect(extraction.data).toEqual({ project: "Atlas", approved_budget_ils: 42000 });
  expect(extraction.sources).toContainEqual(expect.objectContaining({ document_id: recordId, page_number: 1 }));

  await writeFile(testInfo.outputPath("portfolio-extraction.json"), JSON.stringify(extraction, null, 2) + "\n");

  const isolated = await request.post(`${api}/conversations`, {
    headers,
    data: { workspace_id: empty.id, title: "Wrong workspace", document_ids: [scanId] },
  });
  expect(isolated.status()).toBe(400);
  const conversation = await json<{ id: string }>(await request.post(`${api}/conversations`, {
    headers,
    data: { workspace_id: empty.id, title: "Unsupported question", document_ids: [] },
  }));
  const stream = await request.post(`${api}/conversations/${conversation.id}/messages/stream`, {
    headers,
    data: { message: "What is the Atlas budget?" },
  });
  expect(stream.ok()).toBeTruthy();
  const messages = await json<unknown[]>(await request.get(`${api}/conversations/${conversation.id}/messages`, { headers }));
  expect(messages.at(-1)).toMatchObject({
    role: "assistant",
    status: "complete",
    content: "I couldn't find support for that in the selected documents.",
    citations: [],
  });
});
