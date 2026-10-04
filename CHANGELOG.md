# Changelog

All notable changes to DocMind are documented in this file.

## [1.0.0] - 2026-10-04

### Highlights
- Production-oriented AI document workspace across web and Flutter mobile.
- Grounded RAG with citations, hybrid retrieval, PostgreSQL pgvector/HNSW candidates, deterministic fallback paths, and bilingual evaluation coverage.
- Document ingestion, OCR abstractions, parsing, chunking, table extraction, structured table Q&A, notes, flashcards, quizzes, exports, search, and selection actions.
- Workspace collaboration, invitations, notifications, session controls, password recovery/change, email verification, and logout-all semantics.
- Server-side FREE/PRO/TEAM entitlement enforcement for document, storage, member, processing/OCR, and AI usage limits.
- Local AI support with Ollama-compatible chat and 384-dimensional embeddings plus task-aware fast/strong model routing.
- Flutter mobile parity improvements including persistent auth, uploads, SSE chat, citations, offline study data, account security controls, and Activity Center.
- Production email adapter, rate limiting, malware scanning hooks, audit-oriented service boundaries, and security regression coverage.
- Docker Compose validation, API/Web/Worker images, Playwright critical browser flow, RAG quality thresholds, Flutter release APK/AAB builds, and GitHub Actions release artifacts.

### Release validation
- Main CI passes API migrations, compile checks, lint, typing, tests, and RAG evaluation.
- Web passes lint, typecheck, tests, production build, and browser E2E.
- Flutter passes formatting, analyze, tests, release APK build, and release AAB build.
- Docker Compose stack passes readiness checks and critical end-to-end document workflow validation.

### Notes
- Paid AI provider credentials are not required for the validated local/mock development paths.
- Production deployments should provide production-grade database, object storage, SMTP, secrets, and model-provider configuration as documented in the repository.
