from app.models import Conversation, Flashcard, FlashcardDeck, Note

from .conftest import register


def test_global_search_is_workspace_scoped_and_cross_surface(client, db):
    owner = register(client, "search-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Search Workspace", "kind": "personal"},
    ).json()

    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={
            "file": (
                "quarterly-needle.txt",
                b"Quarterly needle content for global search.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 202, upload.text

    note = Note(
        workspace_id=workspace["id"],
        user_id=owner["user"]["id"],
        title="Needle research note",
        content_markdown="A private needle note.",
        source_links=[],
    )
    conversation = Conversation(
        workspace_id=workspace["id"],
        user_id=owner["user"]["id"],
        title="Needle discussion",
    )
    deck = FlashcardDeck(
        workspace_id=workspace["id"],
        user_id=owner["user"]["id"],
        name="Needle deck",
        language="en",
    )
    db.add_all([note, conversation, deck])
    db.flush()
    db.add(
        Flashcard(
            deck_id=deck.id,
            front="What is the needle concept?",
            back="A searchable flashcard answer.",
            source_citations=[],
        )
    )
    db.commit()

    response = client.post(
        "/api/v1/search/global",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "query": "needle",
            "mode": "keyword",
            "content_types": [
                "documents",
                "conversations",
                "notes",
                "flashcards",
            ],
        },
    )
    assert response.status_code == 200, response.text
    types = {item["type"] for item in response.json()}
    assert {"document", "conversation", "note", "flashcard"} <= types

    stranger = register(client, "search-stranger@example.com")
    denied = client.post(
        "/api/v1/search/global",
        headers={"Authorization": f"Bearer {stranger['access_token']}"},
        json={
            "workspace_id": workspace["id"],
            "query": "needle",
        },
    )
    assert denied.status_code == 403


def test_global_search_exact_mode_does_not_return_partial_phrase(client, db):
    owner = register(client, "search-exact@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Exact Search", "kind": "personal"},
    ).json()

    db.add(
        Note(
            workspace_id=workspace["id"],
            user_id=owner["user"]["id"],
            title="Alpha beta gamma",
            content_markdown="Exact phrase lives here.",
            source_links=[],
        )
    )
    db.commit()

    exact = client.post(
        "/api/v1/search/global",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "query": "beta gamma",
            "mode": "exact",
            "content_types": ["notes"],
        },
    )
    assert exact.status_code == 200
    assert len(exact.json()) == 1

    missing = client.post(
        "/api/v1/search/global",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "query": "alpha gamma",
            "mode": "exact",
            "content_types": ["notes"],
        },
    )
    assert missing.status_code == 200
    assert missing.json() == []
