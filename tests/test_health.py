import respx
import httpx
import pytest


@respx.mock
def test_health_main_app_reachable(client):
    respx.get("http://test-main-app/api/version").mock(
        return_value=httpx.Response(200, json={"version": "1.0.0"})
    )

    resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["main_app_reachable"] is True
    assert "version" in data


@respx.mock
def test_health_main_app_unreachable_network_error(client):
    respx.get("http://test-main-app/api/version").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["main_app_reachable"] is False


@respx.mock
def test_health_main_app_unreachable_server_error(client):
    respx.get("http://test-main-app/api/version").mock(
        return_value=httpx.Response(503)
    )

    resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["main_app_reachable"] is False


def test_health_response_has_request_id_header(client):
    with respx.mock:
        respx.get("http://test-main-app/api/version").mock(
            return_value=httpx.Response(200)
        )
        resp = client.get("/health")

    assert "x-request-id" in resp.headers
