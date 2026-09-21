from .conftest import register


def test_authenticated_invitation_inbox_accept_and_reject(client):
    owner = register(client, "invite-owner@example.com")
    invitee = register(client, "invitee@example.com")
    stranger = register(client, "invite-stranger@example.com")

    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    invitee_headers = {"Authorization": f"Bearer {invitee['access_token']}"}
    stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}

    workspace = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Shared Search Team", "kind": "shared"},
    ).json()

    invitation = client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=owner_headers,
        json={"email": "invitee@example.com", "role": "editor"},
    )
    assert invitation.status_code == 201, invitation.text
    invitation_id = invitation.json()["id"]

    inbox = client.get("/api/v1/workspace-invitations", headers=invitee_headers)
    assert inbox.status_code == 200, inbox.text
    assert [item["id"] for item in inbox.json()] == [invitation_id]
    assert inbox.json()[0]["workspace_name"] == "Shared Search Team"

    denied = client.post(
        f"/api/v1/workspace-invitations/{invitation_id}/accept",
        headers=stranger_headers,
    )
    assert denied.status_code == 403

    accepted = client.post(
        f"/api/v1/workspace-invitations/{invitation_id}/accept",
        headers=invitee_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workspace"]["id"] == workspace["id"]
    assert accepted.json()["workspace"]["role"] == "editor"

    workspaces = client.get("/api/v1/workspaces", headers=invitee_headers)
    assert workspaces.status_code == 200
    assert workspace["id"] in {row["id"] for row in workspaces.json()}

    second = client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=owner_headers,
        json={"email": "invitee@example.com", "role": "viewer"},
    )
    assert second.status_code == 409

    other = register(client, "decline@example.com")
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    decline_invite = client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitations",
        headers=owner_headers,
        json={"email": "decline@example.com", "role": "viewer"},
    )
    assert decline_invite.status_code == 201
    decline_id = decline_invite.json()["id"]

    rejected = client.post(
        f"/api/v1/workspace-invitations/{decline_id}/reject",
        headers=other_headers,
    )
    assert rejected.status_code == 204

    inbox_after = client.get("/api/v1/workspace-invitations", headers=other_headers)
    assert inbox_after.status_code == 200
    assert inbox_after.json() == []
