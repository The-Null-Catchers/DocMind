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
from app.models import Document, DocumentChunk, Embedding, User, Workspace, WorkspaceMember  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.rag import RAGService  # noqa: E402
from app.services.retrieval import RetrievalService  # noqa: E402


def main() -> None:
    dataset = json.loads((ROOT / "scripts" / "evaluation_dataset.json").read_text())
    Base.metadata.create_all(engine)
    db = SessionLocal()
    embedder = HashEmbeddingProvider(384, "hash-384-v1")
    user = User(email="eval@docmind.local", password_hash=hash_password("evaluation-password-strong"), display_name="Evaluator")
    db.add(user); db.flush()
    ws = Workspace(owner_id=user.id, name="Evaluation", slug="evaluation")
    db.add(ws); db.flush(); db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    pairs=[]
    for i, row in enumerate(dataset):
        doc = Document(workspace_id=ws.id, uploaded_by_id=user.id, original_filename=row["document"], title=row["document"], object_key=f"eval/{i}", mime_type="text/plain", file_size=len(row["text"]), content_hash=f"{i:064x}", status="ready", processing_progress=100)
        db.add(doc); db.flush()
        chunk = DocumentChunk(workspace_id=ws.id, document_id=doc.id, chunk_index=0, text=row["text"], page_start=row["page"], page_end=row["page"], token_count=len(row["text"].split()), metadata_json={})
        db.add(chunk); db.flush(); pairs.append((row,doc,chunk))
    vectors = asyncio.run(embedder.embed([chunk.text for _,_,chunk in pairs]))
    for (_,doc,chunk),vector in zip(pairs,vectors,strict=True):
        db.add(Embedding(workspace_id=ws.id, document_id=doc.id, chunk_id=chunk.id, provider=embedder.name, model=embedder.model, dimension=384, vector_json=vector))
    db.commit()

    retrieval_ok=0; citation_ok=0; unsupported=0
    for row, _doc, _chunk in pairs:
        hits = asyncio.run(RetrievalService(db, embedder).search(workspace_id=ws.id, query=row["question"], limit=3))
        if any(h.page_number == row["expected_page"] and h.document_title == row["document"] for h in hits):
            retrieval_ok += 1
        result = asyncio.run(RAGService(db).answer(workspace_id=ws.id, question=row["question"]))
        if any(c.page_number == row["expected_page"] and c.document_name == row["document"] for c in result.citations):
            citation_ok += 1
        if not result.citations:
            unsupported += 1
    n=len(dataset)
    print(f"retrieval_accuracy={retrieval_ok/n:.3f}")
    print(f"citation_accuracy={citation_ok/n:.3f}")
    print(f"unsupported_claim_rate={unsupported/n:.3f}")
    db.close()


if __name__ == "__main__":
    main()
