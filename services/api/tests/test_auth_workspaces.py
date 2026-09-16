from .conftest import register


def test_register_login_and_workspace_isolation(client):
    first = register(client, "first@example.com")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    created = client.post("/api/v1/workspaces", headers=first_headers, json={"name": "Research", "kind": "personal"})
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    second = register(client, "second@example.com")
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    denied = client.get(f"/api/v1/workspaces/{workspace_id}", headers=second_headers)
    assert denied.status_code == 403

    allowed = client.get(f"/api/v1/workspaces/{workspace_id}", headers=first_headers)
    assert allowed.status_code == 200


def test_refresh_rotates_token(client):
    auth = register(client)
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": auth["refresh_token"]})
    assert refreshed.status_code == 200
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": auth["refresh_token"]})
    assert replay.status_code == 401
