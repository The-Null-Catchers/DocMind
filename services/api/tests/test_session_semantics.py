from .conftest import register


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_logout_revokes_only_current_session_and_logout_all_revokes_rest(client):
    registered = register(client, "sessions@example.com")
    first_access = registered["access_token"]

    second = client.post(
        "/api/v1/auth/login",
        json={
            "email": "sessions@example.com",
            "password": "correct-horse-battery-staple",
            "device_name": "Second device",
        },
    )
    assert second.status_code == 200, second.text
    second_access = second.json()["access_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(second_access),
    )
    assert logout.status_code == 204

    assert client.get("/api/v1/auth/me", headers=auth_header(second_access)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth_header(first_access)).status_code == 200

    logout_all = client.post(
        "/api/v1/auth/logout-all",
        headers=auth_header(first_access),
    )
    assert logout_all.status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth_header(first_access)).status_code == 401


def test_change_password_keeps_current_session_and_revokes_other_sessions(client):
    registered = register(client, "change-password@example.com")
    current_access = registered["access_token"]

    second = client.post(
        "/api/v1/auth/login",
        json={
            "email": "change-password@example.com",
            "password": "correct-horse-battery-staple",
            "device_name": "Other device",
        },
    )
    assert second.status_code == 200
    other_access = second.json()["access_token"]

    wrong = client.post(
        "/api/v1/auth/password/change",
        headers=auth_header(current_access),
        json={
            "current_password": "wrong-password",
            "new_password": "new-correct-horse-battery-staple",
        },
    )
    assert wrong.status_code == 400

    changed = client.post(
        "/api/v1/auth/password/change",
        headers=auth_header(current_access),
        json={
            "current_password": "correct-horse-battery-staple",
            "new_password": "new-correct-horse-battery-staple",
        },
    )
    assert changed.status_code == 204, changed.text

    assert client.get("/api/v1/auth/me", headers=auth_header(current_access)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth_header(other_access)).status_code == 401

    old_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "change-password@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "change-password@example.com",
            "password": "new-correct-horse-battery-staple",
        },
    )
    assert new_login.status_code == 200
