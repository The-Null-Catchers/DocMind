from .conftest import register


def test_selection_actions_verify_source_and_preserve_citations(client):
    owner = register(client, "selection-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Selections", "kind": "personal"},
    ).json()

    source_text = "DocMind verifies selected text against the persisted document page before running an AI action."
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={"file": ("selection.txt", source_text.encode(), "text/plain")},
    )
    assert upload.status_code == 202, upload.text
    document = upload.json()

    selected = "verifies selected text against the persisted document page"
    explain = client.post(
        "/api/v1/ai/selection",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "selected_text": selected,
            "action": "explain",
        },
    )
    assert explain.status_code == 200, explain.text
    generated = explain.json()
    assert generated["kind"] == "generation"
    assert generated["citation"]["document_id"] == document["id"]
    assert generated["citation"]["page_number"] == 1
    assert generated["citation"]["source_excerpt"] == selected

    invalid = client.post(
        "/api/v1/ai/selection",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "selected_text": "This text does not exist in the source page.",
            "action": "summarize",
        },
    )
    assert invalid.status_code == 422

    flashcard = client.post(
        "/api/v1/ai/selection",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "selected_text": selected,
            "action": "create_flashcard",
        },
    )
    assert flashcard.status_code == 200, flashcard.text
    due = client.get(
        "/api/v1/flashcards/due",
        headers=headers,
        params={"workspace_id": workspace["id"]},
    )
    assert due.status_code == 200
    created_card = next(row for row in due.json() if row["id"] == flashcard.json()["card_id"])
    assert created_card["sources"][0]["document_id"] == document["id"]
    assert created_card["sources"][0]["page_number"] == 1

    note = client.post(
        "/api/v1/ai/selection",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "selected_text": selected,
            "action": "add_to_notes",
        },
    )
    assert note.status_code == 200, note.text
    notes = client.get(
        "/api/v1/notes",
        headers=headers,
        params={"workspace_id": workspace["id"]},
    )
    assert notes.status_code == 200
    created_note = next(row for row in notes.json() if row["id"] == note.json()["note_id"])
    assert created_note["source_links"][0]["document_id"] == document["id"]
    assert created_note["source_links"][0]["page_number"] == 1

    usage = client.get(
        "/api/v1/usage",
        headers=headers,
        params={"workspace_id": workspace["id"]},
    )
    assert usage.status_code == 200
    assert usage.json()["usage"]["ai_messages"] == 1

    stranger = register(client, "selection-stranger@example.com")
    denied = client.post(
        "/api/v1/ai/selection",
        headers={"Authorization": f"Bearer {stranger['access_token']}"},
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "selected_text": selected,
            "action": "explain",
        },
    )
    assert denied.status_code == 403
