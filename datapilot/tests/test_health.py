from app import main
from fastapi.testclient import TestClient

client = TestClient(main.app)


def test_liveness_and_request_id():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_readiness_reports_unavailable_without_leaking_secrets(monkeypatch):
    def missing():
        raise ValueError("secret-connection-string")

    monkeypatch.setattr(main, "get_settings", missing)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"configuration": False}}
    assert "secret-connection-string" not in response.text


def test_readiness_requires_every_dependency(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: object())
    monkeypatch.setattr(
        main,
        "check_dependencies",
        lambda _: {
            "postgres": True,
            "redis": False,
            "object_store": True,
        },
    )
    assert client.get("/health/ready").status_code == 503
    monkeypatch.setattr(
        main,
        "check_dependencies",
        lambda _: {
            "postgres": True,
            "redis": True,
            "object_store": True,
        },
    )
    assert client.get("/health/ready").status_code == 200


def test_unimplemented_business_api_is_not_exposed():
    assert client.get("/api/v1/datasets").status_code == 404
