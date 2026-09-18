from fastapi.testclient import TestClient

from ara.main import create_app


def test_application_factory_serves_api() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "ARA API"}
