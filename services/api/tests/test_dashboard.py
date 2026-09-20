from .conftest import register


def _headers(auth: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_dashboard_uses_real_workspace_data_and_is_isolated(client):
    owner = register(client, "dashboard-owner@example.com")
    headers = _headers(owner)
    workspace_response = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Dashboard workspace", "kind": "personal"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    source = b"DocMind dashboard metrics come from persisted workspace data."
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={"file": ("dashboard.txt", source, "text/plain")},
    )
    assert upload.status_code == 202, upload.text
    document = upload.json()

    conversation = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "title": "Dashboard conversation",
            "document_ids": [document["id"]],
        },
    )
    assert conversation.status_code == 201

    with client.stream(
        "POST",
        f"/api/v1/conversations/{conversation.json()['id']}/messages/stream",
        headers=headers,
        json={
            "message": "What do the dashboard metrics use?",
            "document_ids": [document["id"]],
            "language": "en",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: done" in body

    flashcards = client.post(
        "/api/v1/flashcards/generate",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_ids": [document["id"]],
            "language": "en",
            "count": 1,
            "difficulty": "medium",
        },
    )
    assert flashcards.status_code == 201, flashcards.text

    quiz = client.post(
        "/api/v1/quizzes/generate",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_ids": [document["id"]],
            "language": "en",
            "count": 1,
            "difficulty": "medium",
        },
    )
    assert quiz.status_code == 201, quiz.text

    dashboard = client.get(
        f"/api/v1/dashboard?workspace_id={workspace['id']}",
        headers=headers,
    )
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()

    assert payload["documents"]["total"] == 1
    assert payload["documents"]["ready"] == 1
    assert payload["documents"]["storage_bytes"] == len(source)
    assert payload["documents"]["processed_pages"] >= 1
    assert payload["documents"]["recent"][0]["id"] == document["id"]
    assert payload["documents"]["processing_items"] == []
    assert payload["conversations"][0]["title"] == "Dashboard conversation"
    assert payload["study"]["due_flashcards"] == 1
    assert payload["study"]["recent_quizzes"][0]["id"] == quiz.json()["quiz_id"]
    assert payload["usage"]["ai_messages"] == 1
    assert any(item["action"] == "document.uploaded" for item in payload["activity"])

    stranger = register(client, "dashboard-stranger@example.com")
    denied = client.get(
        f"/api/v1/dashboard?workspace_id={workspace['id']}",
        headers=_headers(stranger),
    )
    assert denied.status_code == 403
