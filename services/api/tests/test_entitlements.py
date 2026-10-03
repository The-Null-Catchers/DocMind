from app.services.entitlements import (
    PLANS,
    PlanEntitlements,
    monthly_usage,
    record_document_processing_usage,
)

from .conftest import register


def _workspace(client, headers, name: str = "Quota Workspace") -> dict:
    response = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": name, "kind": "personal"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _free_plan(**overrides) -> PlanEntitlements:
    current = PLANS["free"]
    values = current.__dict__.copy()
    values.update(overrides)
    return PlanEntitlements(**values)


def test_document_count_limit_is_enforced_server_side(client, monkeypatch):
    owner = register(client, "quota-docs@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = _workspace(client, headers)
    monkeypatch.setitem(PLANS, "free", _free_plan(max_documents=1))

    first = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={"file": ("one.txt", b"first unique document", "text/plain")},
    )
    assert first.status_code == 202, first.text

    second = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={"file": ("two.txt", b"second unique document", "text/plain")},
    )
    assert second.status_code == 403, second.text
    assert second.json()["error"]["code"] == "entitlement_exceeded"
    assert second.json()["error"]["metric"] == "documents"


def test_workspace_member_limit_blocks_new_invitation(client, monkeypatch):
    owner = register(client, "quota-members@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = _workspace(client, headers, "Member Quota")
    monkeypatch.setitem(PLANS, "free", _free_plan(max_members=1))

    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=headers,
        json={"email": "invitee@example.com", "role": "viewer"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["metric"] == "workspace_members"


def test_ai_request_limit_blocks_generation_before_provider_call(client, monkeypatch):
    owner = register(client, "quota-ai@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = _workspace(client, headers, "AI Quota")
    monkeypatch.setitem(PLANS, "free", _free_plan(max_ai_messages_month=0))

    response = client.post(
        "/api/v1/summaries/generate",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_ids": ["00000000-0000-0000-0000-000000000001"],
            "language": "auto",
            "style": "short",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["metric"] == "ai_messages"


def test_processing_usage_replaces_same_document_monthly_record(client, db):
    owner = register(client, "quota-usage@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = _workspace(client, headers, "Usage Idempotency")

    record_document_processing_usage(
        db,
        workspace_id=workspace["id"],
        document_id="document-1",
        processed_pages=8,
        ocr_pages=3,
    )
    db.commit()
    record_document_processing_usage(
        db,
        workspace_id=workspace["id"],
        document_id="document-1",
        processed_pages=5,
        ocr_pages=2,
    )
    db.commit()

    assert monthly_usage(db, workspace["id"], "processed_pages") == 5
    assert monthly_usage(db, workspace["id"], "ocr_pages") == 2
