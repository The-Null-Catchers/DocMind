# DocMind portfolio roadmap

Baseline reviewed on November 17, 2026. Repository roadmap published on November 18, 2026.

This roadmap applies to this repository and follows the shared Null Catchers portfolio plan. Verify the documented state against the current code and runs before starting work.

**Estimated initial demo effort** 25–40 hours for a developer familiar with the project. The estimate excludes external reviews, store accounts, target environment setup, and later milestones.

## Project priorities

**Documented state** The project supports Arabic and English OCR, hybrid retrieval, page citations, structured extraction, study tools, and workspace isolation. The default deterministic providers require no paid credentials. Real model quality requires separate evaluation.

**P0 — Demo** Close the cross-language citation gap and version the OCR and extraction evidence.

**P1 — Validation and depth** Expand the benchmark with known answers and pages. Measure retrieval, citation accuracy, abstention, and latency. Compare a real provider with the mock when available, including Ollama if the hardware supports it.

**P2 — Later** Use evaluation failures to decide whether to add reranking, document comparison, or bounding boxes.

**Acceptance criteria** Evidence includes reproducible data and questions, valid citations, a workspace isolation check, and the provider configuration and revision for all metrics.

**Demo scenario** Ask an Arabic question about a scanned document → open its page citation → compare a table → ask an unsupported question. [README](https://github.com/The-Null-Catchers/DocMind/blob/main/README.md), [RAG](https://github.com/The-Null-Catchers/DocMind/blob/main/docs/rag.md).

CI evaluates document and page matches and explicit abstention on synthetic fixtures with the mock provider.

## Next milestones

[PR #31](https://github.com/The-Null-Catchers/DocMind/pull/31) added Arabic OCR, tables, JSON extraction, and a workspace isolation check. In [PR #32](https://github.com/The-Null-Catchers/DocMind/pull/32), all eight answerable cases retrieved the expected pages, seven cited the expected page, and an empty-workspace question produced an abstention. [Browser evidence](https://github.com/The-Null-Catchers/DocMind/actions/runs/44315521680).

1. [ ] Check page ranking for the English budget question against the Arabic Atlas document. Keep fixture text and provider constant, confirm the budget cites page 2, and confirm the training question still cites page 3.
2. [ ] Test an unsupported question in a populated workspace with unrelated documents. Require an explicit abstention, zero citations, and continued workspace isolation.
3. [ ] Link evaluation and recording evidence to a release. Record the provider, fixture data, and reproduction steps, and settle licensing before distribution.

## Portfolio acceptance checklist

- [ ] Another person can reproduce the primary workflow from a clean checkout using the README and test credentials or fixtures.
- [ ] The demo tells one complete story with a defined user, problem, and saved result.
- [ ] Tests cover the main flow, an important failure, and access boundaries when multiple accounts are involved.
- [ ] Demo data is labeled synthetic and reproducible. Review screenshots and recordings for secrets and customer data.
- [ ] Include four to six real screenshots where appropriate, a 60–120 second recording, and working links. Identify the revision used for capture.
- [ ] The README describes implemented capabilities, setup, architecture, limits, tests, and the demo.
- [ ] A short case study explains two engineering decisions, a considered alternative, and how the system handles an actual failure.
- [ ] Release evidence records the commit SHA, CI, prerequisites, and limits. Performance data includes workload, hardware, and method.
- [ ] Licensing and contributor attribution are settled before distribution. Choose the license for each repository individually.

A hosted demo is optional. Code execution, server administration, and secret management can be demonstrated through a recording and a reproducible isolated environment. Keep public demo access scoped to the activities it needs.

## Implementation and follow-up

- Break P0 into tasks with expected behavior, acceptance criteria, and a suitable test.
- Verify existing functionality first. Update this plan when evidence tied to a commit or PR closes a milestone.
- Record the fixture source, the revision used for evidence, and the tested limits.
- Review the final diff and verify required checks for its exact SHA before merging. Follow branch protection.
- For documentation-only changes with no applicable workflow, verify content and links and record the checks actually performed.
- Tie performance, security, and readiness claims to supporting evidence.
