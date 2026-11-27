import asyncio

import httpx

from app.api import routes
from app.main import app


async def request(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_health_endpoint_reports_liveness() -> None:
    response = asyncio.run(request("/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_unavailable_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(routes, "check_database", lambda: False)
    monkeypatch.setattr(routes, "check_qdrant", lambda: False)

    response = asyncio.run(request("/ready"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {
            "postgresql": {"status": "unavailable"},
            "qdrant": {"status": "unavailable"},
        },
    }
