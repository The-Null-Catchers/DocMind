#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_SECRET"] = "evaluation-secret"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["LLM_PROVIDER"] = "mock"

from app.ai.providers import HashEmbeddingProvider  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Document,
    DocumentChunk,
    Embedding,
    User,
    Workspace,
    WorkspaceMember,
)
from app.security import hash_password  # noqa: E402
from app.services.rag import RAGService  # noqa: E402
from app.services.retrieval import RetrievalService  # noqa: E402


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    payload = json.loads((ROOT / "scripts" / "evaluation_dataset.json").read_text())
    documents = payload["documents"]
    cases = payload["cases"]

    Base.metadata.create_all(engine)
    db = SessionLocal()
    embedder = HashEmbeddingProvider(384, "hash-384-v1")

    user = User(
        email="eval@docmind.local",
        password_hash=hash_password("evaluation-password-strong"),
        display_name="Evaluator",
    )
    db.add(user)
    db.flush()

    workspaces: dict[str, Workspace] = {}
    for key in {row["workspace"] for row in documents} | {row["workspace"] for row in cases}:
        workspace = Workspace(owner_id=user.id, name=f"Evaluation {key}", slug=f"evaluation-{key}")
        db.add(workspace)
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        workspaces[key] = workspace

    seeded: dict[str, tuple[Document, DocumentChunk]] = {}
    for index, row in enumerate(documents):
        workspace = workspaces[row["workspace"]]
        document = Document(
            workspace_id=workspace.id,
            uploaded_by_id=user.id,
            original_filename=row["document"],
            title=row["document"],
            object_key=f"eval/{index}",
            mime_type="text/plain",
            file_size=len(row["text"].encode("utf-8")),
            content_hash=f"{index:064x}",
            status="ready",
            processing_progress=100,
        )
        db.add(document)
        db.flush()
        chunk = DocumentChunk(
            workspace_id=workspace.id,
            document_id=document.id,
            chunk_index=0,
            text=row["text"],
            page_start=row["page"],
            page_end=row["page"],
            token_count=len(row["text"].split()),
            metadata_json={"evaluation_id": row["id"]},
        )
        db.add(chunk)
        db.flush()
        seeded[row["id"]] = (document, chunk)

    chunks = [chunk for _document, chunk in seeded.values()]
    vectors = asyncio.run(embedder.embed([chunk.text for chunk in chunks]))
    for (document, chunk), vector in zip(seeded.values(), vectors, strict=True):
        db.add(
            Embedding(
                workspace_id=document.workspace_id,
                document_id=document.id,
                chunk_id=chunk.id,
                provider=embedder.name,
                model=embedder.model,
                dimension=384,
                vector_json=vector,
            )
        )
    db.commit()

    retrieval_cases = 0
    retrieval_passes = 0
    reciprocal_rank_total = 0.0
    expected_source_count = 0
    retrieved_source_count = 0
    valid_citations = 0
    total_citations = 0
    unsupported_cases = 0
    unsupported_with_citations = 0

    for case in cases:
        workspace = workspaces[case["workspace"]]
        expected_ids = case.get("expected_documents", [])
        expected_document_ids = {
            seeded[item][0].id for item in expected_ids
        }
        expected_source_count += len(expected_document_ids)

        hits = asyncio.run(
            RetrievalService(db, embedder).search(
                workspace_id=workspace.id,
                query=case["question"],
                mode=case.get("mode", "hybrid"),
                exact_phrase=case.get("mode") == "exact",
                limit=8,
            )
        )
        hit_ids = [hit.document_id for hit in hits]

        if expected_document_ids:
            retrieval_cases += 1
            found = expected_document_ids & set(hit_ids)
            retrieved_source_count += len(found)
            if found == expected_document_ids:
                retrieval_passes += 1
            first_rank = next(
                (rank for rank, hit_id in enumerate(hit_ids, start=1) if hit_id in expected_document_ids),
                None,
            )
            if first_rank:
                reciprocal_rank_total += 1.0 / first_rank

        rag_result = asyncio.run(
            RAGService(db).answer(
                workspace_id=workspace.id,
                question=case["question"],
            )
        )
        for citation in rag_result.citations:
            total_citations += 1
            if citation.document_id in expected_document_ids:
                valid_citations += 1

        if case.get("expected_supported", True) is False:
            unsupported_cases += 1
            if rag_result.citations:
                unsupported_with_citations += 1

    primary = workspaces["primary"]
    canary_hits = asyncio.run(
        RetrievalService(db, embedder).search(
            workspace_id=primary.id,
            query="violet-orbit-7391",
            mode="exact",
            exact_phrase=True,
            limit=8,
        )
    )
    workspace_isolation_ok = all(
        hit.document_id != seeded["isolated-secret"][0].id for hit in canary_hits
    )
    if not workspace_isolation_ok:
        raise SystemExit("workspace_isolation=FAILED")

    print(f"retrieval_accuracy={_ratio(retrieval_passes, retrieval_cases):.3f}")
    print(f"citation_accuracy={_ratio(valid_citations, total_citations):.3f}")
    print(
        "unsupported_claim_rate="
        f"{_ratio(unsupported_with_citations, unsupported_cases):.3f}"
    )
    print(f"mrr={_ratio(reciprocal_rank_total, retrieval_cases):.3f}")
    print(
        "source_coverage="
        f"{_ratio(retrieved_source_count, expected_source_count):.3f}"
    )
    print("workspace_isolation=1.000")
    print(f"evaluated_cases={len(cases)}")
    db.close()


if __name__ == "__main__":
    main()
