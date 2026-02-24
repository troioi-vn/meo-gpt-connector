import json

import httpx
import respx

from src.core.jwt import create_jwt


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id=9, sanctum_token='sanctum-token')}"}


@respx.mock
def test_list_weights(client):
    respx.get("http://test-main-app/api/pets/1/weights").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 20, "weight_kg": 4.5, "record_date": "2024-06-01"}],
        )
    )

    resp = client.get("/pets/1/weights", headers=_auth_headers())

    assert resp.status_code == 200
    assert resp.json()[0]["weight_kg"] == 4.5


@respx.mock
def test_create_weight_with_measured_at(client):
    route = respx.post("http://test-main-app/api/pets/1/weights").mock(
        return_value=httpx.Response(
            201,
            json={"id": 21, "weight_kg": 4.5, "record_date": "2024-06-01"},
        )
    )

    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": 4.5, "measured_at": "2024-06-01"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    body = json.loads(route.calls[0].request.content)
    assert body["weight_kg"] == 4.5
    assert body["record_date"] == "2024-06-01"
    assert "measured_at" not in body


@respx.mock
def test_create_weight_without_measured_at_defaults_to_today(client):
    route = respx.post("http://test-main-app/api/pets/1/weights").mock(
        return_value=httpx.Response(201, json={"id": 22, "weight_kg": 3.8})
    )

    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": 3.8},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    body = json.loads(route.calls[0].request.content)
    assert "record_date" in body
    # must be a valid ISO date string
    from datetime import date
    date.fromisoformat(body["record_date"])


@respx.mock
def test_create_weight_invalid_zero(client):
    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": 0},
        headers=_auth_headers(),
    )

    assert resp.status_code == 422


@respx.mock
def test_create_weight_invalid_negative(client):
    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": -1.5},
        headers=_auth_headers(),
    )

    assert resp.status_code == 422


@respx.mock
def test_create_weight_invalid_too_large(client):
    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": 1001.0},
        headers=_auth_headers(),
    )

    assert resp.status_code == 422


@respx.mock
def test_create_weight_valid_boundary_values(client):
    route = respx.post("http://test-main-app/api/pets/1/weights").mock(
        return_value=httpx.Response(201, json={"id": 23})
    )

    # Just above zero
    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": 0.01, "measured_at": "2024-06-01"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201

    # At max boundary
    resp = client.post(
        "/pets/1/weights",
        json={"weight_kg": 1000.0, "measured_at": "2024-06-01"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201


@respx.mock
def test_update_weight(client):
    route = respx.put("http://test-main-app/api/pets/1/weights/20").mock(
        return_value=httpx.Response(200, json={"id": 20, "weight_kg": 5.0})
    )

    resp = client.patch(
        "/pets/1/weights/20",
        json={"weight_kg": 5.0},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    body = json.loads(route.calls[0].request.content)
    assert body == {"weight_kg": 5.0}
    assert "record_date" not in body


@respx.mock
def test_update_weight_maps_measured_at_to_record_date(client):
    route = respx.put("http://test-main-app/api/pets/1/weights/20").mock(
        return_value=httpx.Response(200, json={"id": 20})
    )

    resp = client.patch(
        "/pets/1/weights/20",
        json={"measured_at": "2024-07-15"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    body = json.loads(route.calls[0].request.content)
    assert body == {"record_date": "2024-07-15"}
