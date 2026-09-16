#!/usr/bin/env python3
from __future__ import annotations
import asyncio, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'/'api'))
from app.db import Base, SessionLocal, engine
from app.models import Document, User, Workspace, WorkspaceMember
from app.security import hash_password
from app.services.processing import DocumentProcessingService
from app.services.storage import get_storage

SAMPLES={
  'Hybrid Retrieval Notes.txt': 'Hybrid Retrieval\n\nSemantic search improves conceptual recall. Keyword retrieval preserves exact names, identifiers, and phrases. Reranking combines the candidate sets before context construction.',
  'Arabic OCR Study.txt': 'Arabic OCR Study\n\nتوضح الدراسة أن جودة الصور واتجاه النص يؤثران على دقة التعرف البصري على الحروف. يجب الاحتفاظ برقم الصفحة لربط الإجابة بالمصدر.',
  'Project Atlas Brief.txt': 'Project Atlas\n\nLaunch date: 20 November 2026\nOwner: Research Team\nGoal: Evaluate citation-grounded document assistants using synthetic private corpora.'
}
async def seed():
  Base.metadata.create_all(engine); db=SessionLocal()
  user=User(email='demo@docmind.local',password_hash=hash_password('docmind-demo-password'),display_name='Demo Researcher',locale='en',is_email_verified=True)
  db.add(user);db.flush();ws=Workspace(owner_id=user.id,name='Research Lab',slug='research-lab');db.add(ws);db.flush();db.add(WorkspaceMember(workspace_id=ws.id,user_id=user.id,role='owner'));db.commit()
  for i,(name,text) in enumerate(SAMPLES.items()):
    data=text.encode(); key=f'workspaces/{ws.id}/demo/{name}';get_storage().put_bytes(key,data,'text/plain')
    doc=Document(workspace_id=ws.id,uploaded_by_id=user.id,original_filename=name,title=name[:-4],object_key=key,mime_type='text/plain',file_size=len(data),content_hash=f'{100+i:064x}',status='pending',processing_progress=0);db.add(doc);db.commit();await DocumentProcessingService(db).process(doc.id)
  print('Demo account: demo@docmind.local / docmind-demo-password')
  db.close()
if __name__=='__main__': asyncio.run(seed())
