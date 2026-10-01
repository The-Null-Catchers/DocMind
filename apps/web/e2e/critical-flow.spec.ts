import { expect, test } from "@playwright/test";

const PDF_BASE64 =
  "JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA2MTIgNzkyIF0gL1BhcmVudCA2IDAgUiAvUmVzb3VyY2VzIDw8Ci9Gb250IDEgMCBSIC9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9QYWdlTW9kZSAvVXNlTm9uZSAvUGFnZXMgNiAwIFIgL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL0F1dGhvciAoYW5vbnltb3VzKSAvQ3JlYXRpb25EYXRlIChEOjIwMjYxMDAxMDEzOTIzKzAwJzAwJykgL0NyZWF0b3IgKGFub255bW91cykgL0tleXdvcmRzICgpIC9Nb2REYXRlIChEOjIwMjYxMDAxMDEzOTIzKzAwJzAwJykgL1Byb2R1Y2VyIChSZXBvcnRMYWIgUERGIExpYnJhcnkgLSBcKG9wZW5zb3VyY2VcKSkgCiAgL1N1YmplY3QgKHVuc3BlY2lmaWVkKSAvVGl0bGUgKHVudGl0bGVkKSAvVHJhcHBlZCAvRmFsc2UKPj4KZW5kb2JqCjYgMCBvYmoKPDwKL0NvdW50IDEgL0tpZHMgWyAzIDAgUiBdIC9UeXBlIC9QYWdlcwo+PgplbmRvYmoKNyAwIG9iago8PAovRmlsdGVyIFsgL0FTQ0lJODVEZWNvZGUgL0ZsYXRlRGVjb2RlIF0gL0xlbmd0aCAyMDAKPj4Kc3RyZWFtCkdhcj9oYjc5K1gmO0IoKzpOO11jIWJrJGtaTGtUUmtiOV8sVkYpbmMyQ1YoJT9VVGwjQWtsdC4wMFhyJzMmLGtzSlc3UEUrPFZxLyJkLF1DZS5JJW1JIVMhTSwkZlowR1M6SEYvOyVbbFxISDdxNztVWkBKNEI5blh0VnAtcUMucGBxTjpxay1BdXNRPEM+JTFYXl50L0crTUlbKSZTQVI+M2Z1QC9ZTlVQaEAwXEhGT1RQaF1nTHVbNWw7ITZHbFguUTQlS34+ZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgOAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwNjEgMDAwMDAgbiAKMDAwMDAwMDA5MiAwMDAwMCBuIAowMDAwMDAwMTk5IDAwMDAwIG4gCjAwMDAwMDAzOTIgMDAwMDAgbiAKMDAwMDAwMDQ2MCAwMDAwMCBuIAowMDAwMDAwNzIxIDAwMDAwIG4gCjAwMDAwMDA3ODAgMDAwMDAgbiAKdHJhaWxlcgo8PAovSUQgCls8M2EzODk3YTM0NDhjM2M5ZjZiZTgxM2NkOTliNWIwYTY+PDNhMzg5N2EzNDQ4YzNjOWY2YmU4MTNjZDk5YjViMGE2Pl0KJSBSZXBvcnRMYWIgZ2VuZXJhdGVkIFBERiBkb2N1bWVudCAtLSBkaWdlc3QgKG9wZW5zb3VyY2UpCgovSW5mbyA1IDAgUgovUm9vdCA0IDAgUgovU2l6ZSA4Cj4+CnN0YXJ0eHJlZgoxMDcwCiUlRU9GCg==";

test("critical grounded document workflow", async ({ page }) => {
  const email = "browser-e2e@docmind.local";
  const password = "correct-horse-battery-staple";

  await page.goto("/register");
  await page.getByLabel("Display name").fill("Browser E2E");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/app(?:\/)?$/);

  const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000/api/v1";
  const workspace = await page.evaluate(async ({ apiBase }) => {
    const accessToken = window.localStorage.getItem("docmind_access_token");
    if (!accessToken) throw new Error("Missing access token after registration");
    const response = await fetch(`${apiBase}/workspaces`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${accessToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ name: "Browser E2E", kind: "personal" }),
    });
    if (!response.ok) {
      throw new Error(`Workspace creation failed: ${response.status}`);
    }
    return response.json() as Promise<{ id: string }>;
  }, { apiBase });

  await page.evaluate((workspaceId) => {
    window.localStorage.setItem(
      "docmind-workspace",
      JSON.stringify({
        state: { activeWorkspaceId: workspaceId },
        version: 0,
      }),
    );
  }, workspace.id);

  await page.goto("/app/documents");
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "cedar-source.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from(PDF_BASE64, "base64"),
  });

  await expect(page.getByText("cedar-source", { exact: true })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({
    timeout: 60_000,
  });

  await page.getByText("cedar-source", { exact: true }).click();
  await expect(page.locator(".react-pdf__Page__textContent span").first()).toBeVisible({
    timeout: 30_000,
  });

  await page
    .getByPlaceholder("Ask about this document…")
    .fill("When is Project Cedar launching?");
  await page.getByRole("button", { name: "Send question" }).click();

  const sourceButton = page.getByRole("button", { name: /Source 1/ }).first();
  await expect(sourceButton).toBeVisible({ timeout: 30_000 });
  await sourceButton.click();
  await expect(page).toHaveURL(/page=1/);

  const textSpan = page.locator(".react-pdf__Page__textContent span").first();
  await textSpan.evaluate((span) => {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(span);
    selection?.removeAllRanges();
    selection?.addRange(range);
    span.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });

  const explain = page.getByRole("button", { name: "Explain" });
  await expect(explain).toBeVisible();
  await explain.click();
  await expect(page.getByText(/Verified against page 1/)).toBeVisible({
    timeout: 30_000,
  });
});
