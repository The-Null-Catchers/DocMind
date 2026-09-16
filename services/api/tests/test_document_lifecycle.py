from pathlib import Path
from .conftest import TEST_STORAGE, register


def test_upload_process_file_access_and_delete(client):
    owner = register(client, "docs-owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    ws = client.post("/api/v1/workspaces", headers=owner_headers, json={"name": "Docs", "kind": "personal"}).json()

    uploaded = client.post(
        "/api/v1/documents/upload",
        headers=owner_headers,
        data={"workspace_id": ws["id"]},
        files={"file": ("notes.txt", b"TITLE:\n\nThe launch date is 4 April. Citations keep page references.", "text/plain")},
    )
    assert uploaded.status_code == 202, uploaded.text
    document_id = uploaded.json()["id"]

    rows = client.get("/api/v1/documents", params={"workspace_id": ws["id"]}, headers=owner_headers)
    assert rows.status_code == 200
    assert rows.json()[0]["status"] == "ready"

    file_response = client.get(f"/api/v1/documents/{document_id}/file", headers=owner_headers)
    assert file_response.status_code == 200
    assert b"launch date" in file_response.content

    stranger = register(client, "stranger@example.com")
    stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}
    denied = client.get(f"/api/v1/documents/{document_id}/file", headers=stranger_headers)
    assert denied.status_code == 403

    deletion = client.delete(f"/api/v1/documents/{document_id}", headers=owner_headers)
    assert deletion.status_code == 204
    assert client.get("/api/v1/documents", params={"workspace_id": ws["id"]}, headers=owner_headers).json() == []
    assert not any(Path(TEST_STORAGE).rglob("notes.txt"))
