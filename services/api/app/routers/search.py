from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import User
from ..schemas import SearchHit, SearchRequest
from ..services.retrieval import RetrievalService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchHit])
async def search(payload: SearchRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SearchHit]:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    hits = await RetrievalService(db).search(
        workspace_id=payload.workspace_id,
        query=payload.query,
        document_ids=payload.document_ids,
        folder_id=payload.folder_id,
        exact_phrase=payload.exact_phrase,
        limit=payload.limit,
    )
    return [SearchHit(
        chunk_id=h.chunk_id,
        document_id=h.document_id,
        document_title=h.document_title,
        page_number=h.page_number,
        section_title=h.section_title,
        excerpt=h.text[:700],
        score=h.score,
        semantic_score=h.semantic_score,
        keyword_score=h.keyword_score,
    ) for h in hits]
