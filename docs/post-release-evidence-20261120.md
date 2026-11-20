# Post-release bilingual portfolio verification (November 2026)

This is an **evidence checkpoint**, not a new published release or a claim that the October 2026 `v1.0.0` tag contains the changes below.

## Exact verified revision and artifacts

- Tested commit: `8f1816487660b6f7b035c051e2dd2669f20f00ab`.
- [Successful CI run 44443076958](https://github.com/The-Null-Catchers/DocMind/actions/runs/44443076958).
- [Browser and evaluation evidence artifact](https://github.com/The-Null-Catchers/DocMind/actions/runs/44443076958/artifacts/14492687093), named `docmind-portfolio-44443076958-1` (GitHub Actions artifact retention applies).
- [PR #38](https://github.com/The-Null-Catchers/DocMind/pull/38): mandatory populated-workspace unsupported-question abstention evaluation.
- [PR #39](https://github.com/The-Null-Catchers/DocMind/pull/39): bilingual page ranking and browser regression.

## Reproduction

Follow [the portfolio demo instructions](portfolio-demo.md) using the synthetic files under `apps/web/e2e/fixtures`. Run `python scripts/evaluate_rag.py` with the API dependencies installed, and the browser scenario `e2e/portfolio.spec.ts` against a disposable Compose instance. The documented default configuration uses Tesseract Arabic/English OCR, hash embeddings, and a deterministic grounded mock answer provider. Confirm the Atlas budget citation points to page 2, the training question to page 3, and unsupported questions in populated/empty workspaces abstain with zero citations. Confirm workspace access boundaries and record the exact fixture and provider configuration when reproducing.

## Limits and remaining release gates

- Results qualify the deterministic synthetic fixtures and mock provider, not an external LLM's real-world answer quality, production latency, or arbitrary scanned documents.
- `v1.0.0` was published on October 4, 2026, before these November improvements. **Do not attach the November evidence to that tag as if it tested those features.**
- Before a new distributable release, review contributor attribution, choose and add an explicit repository license, and create a version/tag at the actual verified source revision. Re-run required checks on that revision and link durable screenshots/recording, artifact and provider/fixture details to the new release.
