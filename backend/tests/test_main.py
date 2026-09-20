from httpx import ASGITransport, AsyncClient

from ara.main import create_app


async def test_application_factory_serves_api() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://testserver"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "ARA API"}
