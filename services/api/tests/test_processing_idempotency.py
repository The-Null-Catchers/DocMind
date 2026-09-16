import asyncio
from sqlalchemy import func, select
from app.models import Document, DocumentChunk, Embedding, User, Workspace, WorkspaceMember
from app.security import hash_password
from app.services.processing import DocumentProcessingService
from app.services.storage import get_storage


def test_retry_does_not_duplicate_chunks_or_embeddings(db):
    user = User(email="proc@example.com", password_hash=hash_password("correct-horse-battery-staple"), display_name="Proc")
    db.add(user); db.flush()
    ws = Workspace(owner_id=user.id, name="Processing", slug="processing")
    db.add(ws); db.flush(); db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    content = b"TITLE:\n\nDocMind preserves citations.\n\nSecond paragraph explains deterministic processing."
    key = f"workspaces/{ws.id}/documents/test/doc.txt"
    get_storage().put_bytes(key, content, "text/plain")
    doc = Document(workspace_id=ws.id, uploaded_by_id=user.id, original_filename="doc.txt", title="doc", object_key=key, mime_type="text/plain", file_size=len(content), content_hash="a"*64, status="pending", processing_progress=0)
    db.add(doc); db.commit()

    asyncio.run(DocumentProcessingService(db).process(doc.id))
    first_chunks = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    first_embeddings = db.scalar(select(func.count()).select_from(Embedding).where(Embedding.document_id == doc.id))
    assert first_chunks and first_embeddings == first_chunks

    doc.status = "processing"; db.commit()
    asyncio.run(DocumentProcessingService(db).process(doc.id))
    second_chunks = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    second_embeddings = db.scalar(select(func.count()).select_from(Embedding).where(Embedding.document_id == doc.id))
    assert second_chunks == first_chunks
    assert second_embeddings == first_embeddings
