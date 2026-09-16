from .conftest import register


def test_password_reset_revokes_old_password(client):
    register(client, "reset@example.com")
    forgot = client.post("/api/v1/auth/password/forgot", json={"email": "reset@example.com"})
    assert forgot.status_code == 202
    token = forgot.json()["dev_token"]
    reset = client.post("/api/v1/auth/password/reset", json={"token": token, "password": "new-correct-horse-battery-staple"})
    assert reset.status_code == 204
    old_login = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "correct-horse-battery-staple"})
    assert old_login.status_code == 401
    new_login = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "new-correct-horse-battery-staple"})
    assert new_login.status_code == 200
