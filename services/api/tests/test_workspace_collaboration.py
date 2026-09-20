from .conftest import register


def _headers(auth: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def _workspace(client, headers, name="Team"):
    response = client.post("/api/v1/workspaces", headers=headers, json={"name": name, "kind": "shared"})
    assert response.status_code == 201, response.text
    return response.json()


def test_workspace_list_exposes_effective_role(client):
    owner = register(client, "role-owner@example.com")
    headers = _headers(owner)
    workspace = _workspace(client, headers)
    response = client.get("/api/v1/workspaces", headers=headers)
    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == workspace["id"])
    assert row["role"] == "owner"


def test_invitation_accept_is_email_bound_and_adds_member(client):
    owner = register(client, "invite-owner@example.com")
    owner_headers = _headers(owner)
    workspace = _workspace(client, owner_headers)

    invited = register(client, "invite-member@example.com")
    invited_headers = _headers(invited)
    stranger = register(client, "invite-stranger@example.com")
    stranger_headers = _headers(stranger)

    created = client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=owner_headers,
        json={"email": "invite-member@example.com", "role": "editor"},
    )
    assert created.status_code == 201, created.text
    token = created.json()["dev_token"]

    denied = client.post(
        "/api/v1/workspace-invitations/accept",
        headers=stranger_headers,
        json={"token": token},
    )
    assert denied.status_code == 403

    accepted = client.post(
        "/api/v1/workspace-invitations/accept",
        headers=invited_headers,
        json={"token": token},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workspace"]["role"] == "editor"

    member_workspaces = client.get("/api/v1/workspaces", headers=invited_headers)
    assert member_workspaces.status_code == 200
    assert any(
        item["id"] == workspace["id"] and item["role"] == "editor"
        for item in member_workspaces.json()
    )


def test_admin_cannot_manage_admins_or_owner(client):
    owner = register(client, "admin-owner@example.com")
    owner_headers = _headers(owner)
    workspace = _workspace(client, owner_headers)

    admin = register(client, "admin-user@example.com")
    admin_headers = _headers(admin)
    editor = register(client, "editor-user@example.com")

    for email, role, auth_headers in [
        ("admin-user@example.com", "admin", admin_headers),
        ("editor-user@example.com", "editor", _headers(editor)),
    ]:
        invitation = client.post(
            f"/api/v1/workspaces/{workspace['id']}/invitations",
            headers=owner_headers,
            json={"email": email, "role": role},
        )
        assert invitation.status_code == 201
        accepted = client.post(
            "/api/v1/workspace-invitations/accept",
            headers=auth_headers,
            json={"token": invitation.json()["dev_token"]},
        )
        assert accepted.status_code == 200

    members = client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=admin_headers)
    assert members.status_code == 200
    rows = {row["email"]: row for row in members.json()}

    promote = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{rows['editor-user@example.com']['user_id']}",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert promote.status_code == 403

    remove_owner = client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner['user']['id']}",
        headers=admin_headers,
    )
    assert remove_owner.status_code == 409


def test_owner_can_change_and_remove_non_owner_member(client):
    owner = register(client, "manage-owner@example.com")
    owner_headers = _headers(owner)
    workspace = _workspace(client, owner_headers)
    member = register(client, "manage-member@example.com")
    member_headers = _headers(member)

    invitation = client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=owner_headers,
        json={"email": "manage-member@example.com", "role": "viewer"},
    )
    assert invitation.status_code == 201
    assert client.post(
        "/api/v1/workspace-invitations/accept",
        headers=member_headers,
        json={"token": invitation.json()["dev_token"]},
    ).status_code == 200

    changed = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{member['user']['id']}",
        headers=owner_headers,
        json={"role": "editor"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "editor"

    removed = client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{member['user']['id']}",
        headers=owner_headers,
    )
    assert removed.status_code == 204

    denied = client.get(f"/api/v1/workspaces/{workspace['id']}", headers=member_headers)
    assert denied.status_code == 403
