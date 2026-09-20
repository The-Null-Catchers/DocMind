from .conftest import register


def test_document_library_supports_search_filters_sorting_and_pagination(client):
    owner = register(client, "library-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Library", "kind": "personal"},
    ).json()

    for name, body, mime in [
        ("beta.md", b"# Beta\nSecond source", "text/markdown"),
        ("alpha.txt", b"Alpha source content", "text/plain"),
    ]:
        response = client.post(
            "/api/v1/documents/upload",
            headers=headers,
            data={"workspace_id": workspace["id"]},
            files={"file": (name, body, mime)},
        )
        assert response.status_code == 202, response.text

    page = client.get(
        "/api/v1/documents/library",
        headers=headers,
        params={
            "workspace_id": workspace["id"],
            "sort": "title",
            "direction": "asc",
            "limit": 1,
            "offset": 0,
        },
    )
    assert page.status_code == 200, page.text
    payload = page.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["title"] == "alpha"
    assert payload["items"][0]["error_message"] is None
    assert "ready" in payload["facets"]["statuses"]
    assert "text/plain" in payload["facets"]["mime_types"]

    searched = client.get(
        "/api/v1/documents/library",
        headers=headers,
        params={"workspace_id": workspace["id"], "q": "BETA"},
    )
    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["title"] == "beta"

    filtered = client.get(
        "/api/v1/documents/library",
        headers=headers,
        params={"workspace_id": workspace["id"], "mime_type": "text/plain"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["original_filename"] == "alpha.txt"

    stranger = register(client, "library-stranger@example.com")
    denied = client.get(
        "/api/v1/documents/library",
        headers={"Authorization": f"Bearer {stranger['access_token']}"},
        params={"workspace_id": workspace["id"]},
    )
    assert denied.status_code == 403
