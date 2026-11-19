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
    documents_by_key: dict[tuple[str, str], Document] = {}
    chunk_counts: dict[tuple[str, str], int] = {}
    for index, row in enumerate(documents):
        key = (row["workspace"], row["document"])
        document = documents_by_key.get(key)
        if document is None:
            document = Document(
                workspace_id=workspaces[row["workspace"]].id,
                uploaded_by_id=user.id,
                original_filename=row["document"],
                title=row["document"],
                object_key=f"eval/{index}",
                mime_type="text/plain",
                file_size=0,
                content_hash=f"{index:064x}",
                status="ready",
                processing_progress=100,
            )
            db.add(document)
            db.flush()
            documents_by_key[key] = document
        document.file_size += len(row["text"].encode("utf-8"))
        chunk_index = chunk_counts.get(key, 0)
        chunk_counts[key] = chunk_index + 1
        chunk = DocumentChunk(
            workspace_id=document.workspace_id,
            document_id=document.id,
            chunk_index=chunk_index,
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
    supported_cases_with_expected_citation = 0
    unsupported_cases = 0
    unsupported_without_abstention = 0
    failed_required_abstentions: list[str] = []
    failed_required_citations: list[str] = []

    for case in cases:
        workspace = workspaces[case["workspace"]]
        expected_ids = case["expected_pages"]
        expected_sources = {
            (seeded[item][0].id, seeded[item][1].page_start) for item in expected_ids
        }
        expected_source_count += len(expected_sources)

        hits = asyncio.run(
            RetrievalService(db, embedder).search(
                workspace_id=workspace.id,
                query=case["question"],
                mode=case.get("mode", "hybrid"),
                exact_phrase=case.get("mode") == "exact",
                limit=8,
            )
        )
        hit_sources = [(hit.document_id, hit.page_number) for hit in hits]

        if expected_sources:
            retrieval_cases += 1
            found = expected_sources & set(hit_sources)
            retrieved_source_count += len(found)
            if found == expected_sources:
                retrieval_passes += 1
            first_rank = next(
                (rank for rank, source in enumerate(hit_sources, start=1) if source in expected_sources),
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
            if (citation.document_id, citation.page_number) in expected_sources:
                valid_citations += 1

        if case.get("expected_supported", True) is False:
            unsupported_cases += 1
            fragment = case["expected_answer_fragment"]
            if rag_result.citations or fragment.casefold() not in rag_result.answer.casefold():
                unsupported_without_abstention += 1
                if case.get("require_abstention", False):
                    failed_required_abstentions.append(case["id"])

        if expected_sources:
            cited_sources = {
                (citation.document_id, citation.page_number)
                for citation in rag_result.citations
            }
            if expected_sources & cited_sources:
                supported_cases_with_expected_citation += 1
            else:
                print(f"missing_expected_citation={case['id']}")
            if case.get("require_citation", False):
                if cited_sources != expected_sources:
                    failed_required_citations.append(case["id"])
                else:
                    print(f"required_citation_verified={case['id']}")

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

    retrieval_accuracy = _ratio(retrieval_passes, retrieval_cases)
    citation_accuracy = _ratio(valid_citations, total_citations)
    supported_citation_rate = _ratio(supported_cases_with_expected_citation, retrieval_cases)
    unsupported_claim_rate = _ratio(unsupported_without_abstention, unsupported_cases)
    mrr = _ratio(reciprocal_rank_total, retrieval_cases)
    source_coverage = _ratio(retrieved_source_count, expected_source_count)

    print(f"retrieval_accuracy={retrieval_accuracy:.3f}")
    print(f"citation_accuracy={citation_accuracy:.3f}")
    print(f"supported_citation_rate={supported_citation_rate:.3f}")
    print(f"unsupported_claim_rate={unsupported_claim_rate:.3f}")
    print(f"mrr={mrr:.3f}")
    print(f"source_coverage={source_coverage:.3f}")
    print("workspace_isolation=1.000")
    print(f"evaluated_cases={len(cases)}")

    thresholds = {
        "retrieval_accuracy": float(os.getenv("RAG_EVAL_MIN_RETRIEVAL", "0.70")),
        "citation_accuracy": float(os.getenv("RAG_EVAL_MIN_CITATION", "0.70")),
        "supported_citation_rate": float(os.getenv("RAG_EVAL_MIN_SUPPORTED_CITATION", "0.70")),
        "unsupported_claim_rate": float(os.getenv("RAG_EVAL_MAX_UNSUPPORTED", "0.25")),
        "source_coverage": float(os.getenv("RAG_EVAL_MIN_SOURCE_COVERAGE", "0.70")),
    }
    failures = [
        f"citations do not match the required pages for {case_id}"
        for case_id in failed_required_citations
    ] + [
        f"required abstention missing for {case_id}" for case_id in failed_required_abstentions
    ]
    if retrieval_accuracy < thresholds["retrieval_accuracy"]:
        failures.append(
            f"retrieval_accuracy {retrieval_accuracy:.3f} < {thresholds['retrieval_accuracy']:.3f}"
        )
    if citation_accuracy < thresholds["citation_accuracy"]:
        failures.append(
            f"citation_accuracy {citation_accuracy:.3f} < {thresholds['citation_accuracy']:.3f}"
        )
    if supported_citation_rate < thresholds["supported_citation_rate"]:
        failures.append(
            f"supported_citation_rate {supported_citation_rate:.3f} < "
            f"{thresholds['supported_citation_rate']:.3f}"
        )
    if unsupported_claim_rate > thresholds["unsupported_claim_rate"]:
        failures.append(
            "unsupported_claim_rate "
            f"{unsupported_claim_rate:.3f} > {thresholds['unsupported_claim_rate']:.3f}"
        )
    if source_coverage < thresholds["source_coverage"]:
        failures.append(
            f"source_coverage {source_coverage:.3f} < {thresholds['source_coverage']:.3f}"
        )

    db.close()
    if failures:
        raise SystemExit("RAG evaluation thresholds failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
