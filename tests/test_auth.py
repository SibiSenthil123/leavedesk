from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_login_returns_a_bearer_token(client: TestClient) -> None:
    r = client.post(
        "/auth/login", data={"username": "priya@leavedesk.dev", "password": PASSWORD}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2  # header.payload.signature


def test_wrong_password_and_unknown_email_give_the_same_401(client: TestClient) -> None:
    wrong_pw = client.post(
        "/auth/login", data={"username": "priya@leavedesk.dev", "password": "nope-nope"}
    )
    no_user = client.post(
        "/auth/login", data={"username": "ghost@leavedesk.dev", "password": "nope-nope"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


def test_protected_route_without_token_is_401(client: TestClient) -> None:
    r = client.get("/leave-requests")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_tampered_token_is_401(client: TestClient, priya: TestClient) -> None:
    token = priya.headers["Authorization"].removeprefix("Bearer ")
    bad = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_me_shows_manager_flag(priya: TestClient, arjun: TestClient) -> None:
    assert priya.get("/auth/me").json()["is_manager"] is False
    assert arjun.get("/auth/me").json()["is_manager"] is True
