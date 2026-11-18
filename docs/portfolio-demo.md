# DocMind bilingual portfolio demo

The [demo fixtures](../apps/web/e2e/fixtures) contain synthetic data. The two-page PDF is raster-only. Page 1 covers an unrelated archive policy, and page 2 gives the Atlas budget in Arabic. The CSV compares Atlas and Cedar. The text record supplies typed fields for structured extraction.

## Run the browser scenario

Start the Compose stack as described in the [README](../README.md), using the default mock LLM, hash embeddings and Tesseract with Arabic and English language data. Then run:

```sh
cd apps/web
npm ci
npm install --no-save --package-lock=false @playwright/test@1.51.1
npx playwright install chromium
npx playwright test e2e/portfolio.spec.ts
```

The scenario creates a disposable account and workspaces. Use a local or test instance. Set `WEB_BASE_URL` and `API_BASE_URL` if your instance uses different ports.

The automated walkthrough uploads the scan through the library, waits for processing, checks that OCR recovered Arabic text and the value `42000`, asks an Arabic question, and follows the citation to page 2. It then verifies the CSV rows, checks JSON extraction of the Atlas record against the expected values and page reference, rejects a cross-workspace document selection, and confirms a question in an empty workspace yields an unsupported answer with no citations.

The Docker CI job uploads successful citation and table screenshots as a workflow artifact tied to the tested revision. The run exercises real OCR and retrieval. The mock answer provider quotes retrieved text, so this scenario does not measure the answer quality of a production language model or its behavior on all unsupported questions.
