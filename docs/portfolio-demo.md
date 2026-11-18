# DocMind bilingual portfolio demo

The [demo fixtures](../apps/web/e2e/fixtures) contain synthetic data. The two-page PDF is raster-only. Page 1 covers an unrelated archive policy, and page 2 gives the Atlas budget in Arabic. The CSV compares Atlas and Cedar. The text record supplies typed fields for structured extraction.

## Run the browser scenario

Start the Compose stack as described in the [README](../README.md), using the default mock LLM, hash embeddings and Tesseract with Arabic and English language data. Run the scenario with these commands.

```sh
cd apps/web
npm ci
npm install --no-save --package-lock=false @playwright/test@1.51.1
npx playwright install chromium
npx playwright test e2e/portfolio.spec.ts
```

The scenario creates a disposable account and workspaces. Use a local or test instance. Set `WEB_BASE_URL` and `API_BASE_URL` if your instance uses different ports.

The automated walkthrough uploads the scan through the library, waits for processing, checks that OCR recovered Arabic text and the value `42000`, asks an Arabic question, and follows the citation to page 2. It then verifies the CSV rows, checks JSON extraction of the Atlas record against the expected values and page reference, rejects a cross-workspace document selection, and confirms a question in an empty workspace yields an unsupported answer with no citations.

The Docker CI job uploads a browser recording, citation and table screenshots, and the validated JSON output as a workflow artifact tied to the tested revision. The run exercises real OCR and retrieval. The mock answer provider quotes retrieved text. The walkthrough measures OCR, retrieval and citation navigation with the supplied files.

Newly processed documents index each page separately so citations can name the page that holds the quoted text. Reprocess older documents and ask the question again to refresh their page references.

### Repeatable retrieval evaluation

Run `python scripts/evaluate_rag.py` from the root with the API dependencies
installed. The benchmark uses synthetic text, the hash embedder, and the
grounded mock answer provider. Retrieval coverage and citation accuracy
match both document and page. The Atlas fixture contains two pages under one
document ID. The supported citation rate also counts answerable cases that
returned no expected citation. The unsupported case requires an explicit abstention and zero
citations. The results measure this fixture and provider configuration.

The Atlas benchmark requires the budget question in English to cite page 2
and the training question in Arabic to cite page 3. The lexical scorer
recognizes a small Arabic–English vocabulary for budget and training
and ignores common question words when other query terms are present.
Exact-phrase search still matches the supplied phrase literally.
