from .conftest import register


def _headers(auth: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_note_exports_run_in_background_and_download_authorized(client):
    owner = register(client, "export-owner@example.com")
    headers = _headers(owner)
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Exports", "kind": "personal"},
    ).json()
    note = client.post(
        "/api/v1/notes",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "title": "Export note",
            "content_markdown": "# Grounded note\n\nExported from DocMind.",
            "source_links": [],
        },
    ).json()

    created = client.post(
        "/api/v1/exports",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "kind": "note_markdown",
            "source_id": note["id"],
        },
    )
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]

    job = client.get(f"/api/v1/exports/{job_id}", headers=headers)
    assert job.status_code == 200
    assert job.json()["status"] == "ready"

    download = client.get(f"/api/v1/exports/{job_id}/file", headers=headers)
    assert download.status_code == 200
    assert b"Grounded note" in download.content
    assert "attachment" in download.headers["content-disposition"]

    stranger = register(client, "export-stranger@example.com")
    denied = client.get(
        f"/api/v1/exports/{job_id}/file",
        headers=_headers(stranger),
    )
    assert denied.status_code == 404


def test_summary_pdf_and_extraction_json_exports(client):
    owner = register(client, "export-payload@example.com")
    headers = _headers(owner)
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Payload exports", "kind": "personal"},
    ).json()

    pdf_job = client.post(
        "/api/v1/exports",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "kind": "summary_pdf",
            "payload": {
                "title": "Synthetic summary",
                "content": "This is a generated summary with source-aware content.",
            },
        },
    )
    assert pdf_job.status_code == 202, pdf_job.text
    pdf_download = client.get(
        f"/api/v1/exports/{pdf_job.json()['id']}/file",
        headers=headers,
    )
    assert pdf_download.status_code == 200
    assert pdf_download.content.startswith(b"%PDF")

    json_job = client.post(
        "/api/v1/exports",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "kind": "extraction_json",
            "payload": {
                "title": "Invoice",
                "data": {"invoice_number": "INV-42", "total": 125.5},
            },
        },
    )
    assert json_job.status_code == 202
    json_download = client.get(
        f"/api/v1/exports/{json_job.json()['id']}/file",
        headers=headers,
    )
    assert json_download.status_code == 200
    assert b"INV-42" in json_download.content
