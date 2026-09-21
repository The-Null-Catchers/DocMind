from app.models import Message
from app.routers.conversations import _persist_interrupted_message

from .conftest import register


def test_interrupted_message_persists_partial_content(client, db):
    auth = register(client, "cancel-owner@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Cancellation", "kind": "personal"},
    ).json()
    conversation = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "title": "Cancellation test",
            "document_ids": [],
        },
    ).json()

    message = Message(
        conversation_id=conversation["id"],
        role="assistant",
        content="",
        status="streaming",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    _persist_interrupted_message(
        db,
        message_id=message.id,
        content="  Partial grounded answer  ",
        status="cancelled",
    )

    db.expire_all()
    persisted = db.get(Message, message.id)
    assert persisted is not None
    assert persisted.content == "Partial grounded answer"
    assert persisted.status == "cancelled"
