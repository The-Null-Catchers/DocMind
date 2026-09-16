import asyncio
from app.ai.providers import HashEmbeddingProvider
from app.models import Document, DocumentChunk, Embedding, User, Workspace, WorkspaceMember
from app.security import hash_password
from app.services.retrieval import RetrievalService


def _seed_workspace(db, owner_email: str, workspace_name: str, text: str):
    user = User(email=owner_email, password_hash=hash_password("correct-horse-battery-staple"), display_name=owner_email)
    db.add(user); db.flush()
    workspace = Workspace(owner_id=user.id, name=workspace_name, slug=workspace_name.lower())
    db.add(workspace); db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    doc = Document(
        workspace_id=workspace.id, uploaded_by_id=user.id, original_filename="doc.txt", title=workspace_name,
        object_key=f"{workspace.id}/doc.txt", mime_type="text/plain", file_size=len(text), content_hash=(workspace.id.replace('-', '') + '0'*64)[:64], status="ready", processing_progress=100,
    )
    db.add(doc); db.flush()
    chunk = DocumentChunk(workspace_id=workspace.id, document_id=doc.id, chunk_index=0, text=text, page_start=1, page_end=1, token_count=10, metadata_json={})
    db.add(chunk); db.flush()
    return workspace, doc, chunk


def test_retrieval_never_crosses_workspace(db):
    embedder = HashEmbeddingProvider(384, "hash-384-v1")
    ws_a, doc_a, chunk_a = _seed_workspace(db, "a@example.com", "Alpha", "Orchid protocol launch date is April 4.")
    ws_b, doc_b, chunk_b = _seed_workspace(db, "b@example.com", "Beta", "Orchid protocol secret budget is 900 million.")
    va, vb = asyncio.run(embedder.embed([chunk_a.text, chunk_b.text]))
    db.add_all([
        Embedding(workspace_id=ws_a.id, document_id=doc_a.id, chunk_id=chunk_a.id, provider=embedder.name, model=embedder.model, dimension=384, vector_json=va),
        Embedding(workspace_id=ws_b.id, document_id=doc_b.id, chunk_id=chunk_b.id, provider=embedder.name, model=embedder.model, dimension=384, vector_json=vb),
    ])
    db.commit()
    hits = asyncio.run(RetrievalService(db, embedder).search(workspace_id=ws_a.id, query="Orchid secret budget", limit=10))
    assert hits
    assert all(hit.document_id == doc_a.id for hit in hits)
    assert all("900 million" not in hit.text for hit in hits)
