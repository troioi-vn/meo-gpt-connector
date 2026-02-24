import json

import httpx
import respx

from src.core.jwt import create_jwt


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id=9, sanctum_token='sanctum-token')}"}


@respx.mock
def test_list_medical_records(client):
    respx.get("http://test-main-app/api/pets/1/medical-records").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 5, "record_type": "checkup", "record_date": "2024-05-10"}],
        )
    )

    resp = client.get("/pets/1/medical-records", headers=_auth_headers())

    assert resp.status_code == 200
    assert resp.json()[0]["record_type"] == "checkup"


@respx.mock
def test_create_medical_record_known_type(client):
    route = respx.post("http://test-main-app/api/pets/1/medical-records").mock(
        return_value=httpx.Response(
            201,
            json={"id": 6, "record_type": "checkup", "record_date": "2024-06-01"},
        )
    )

    resp = client.post(
        "/pets/1/medical-records",
        json={"record_type": "checkup", "record_date": "2024-06-01", "vet_name": "Dr. Smith"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    body = json.loads(route.calls[0].request.content)
    assert body["record_type"] == "checkup"
    assert body["vet_name"] == "Dr. Smith"


@respx.mock
def test_create_medical_record_unknown_type_coerced_to_other(client):
    """Unknown record_type values must degrade to 'other' without crashing."""
    route = respx.post("http://test-main-app/api/pets/1/medical-records").mock(
        return_value=httpx.Response(201, json={"id": 7, "record_type": "other"})
    )

    resp = client.post(
        "/pets/1/medical-records",
        json={"record_type": "mystery_type", "record_date": "2024-06-01"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    body = json.loads(route.calls[0].request.content)
    assert body["record_type"] == "other"


@respx.mock
def test_create_medical_record_default_type_is_other(client):
    """When record_type is omitted entirely, default to 'other'."""
    route = respx.post("http://test-main-app/api/pets/1/medical-records").mock(
        return_value=httpx.Response(201, json={"id": 8, "record_type": "other"})
    )

    resp = client.post(
        "/pets/1/medical-records",
        json={"record_date": "2024-06-01", "description": "General check"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    body = json.loads(route.calls[0].request.content)
    assert body["record_type"] == "other"


@respx.mock
def test_update_medical_record_coerces_unknown_type(client):
    route = respx.put("http://test-main-app/api/pets/1/medical-records/5").mock(
        return_value=httpx.Response(200, json={"id": 5, "record_type": "other"})
    )

    resp = client.patch(
        "/pets/1/medical-records/5",
        json={"record_type": "alien_procedure"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    body = json.loads(route.calls[0].request.content)
    assert body["record_type"] == "other"


@respx.mock
def test_update_medical_record_known_type_passes_through(client):
    route = respx.put("http://test-main-app/api/pets/1/medical-records/5").mock(
        return_value=httpx.Response(200, json={"id": 5, "record_type": "surgery"})
    )

    resp = client.patch(
        "/pets/1/medical-records/5",
        json={"record_type": "surgery"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    body = json.loads(route.calls[0].request.content)
    assert body["record_type"] == "surgery"


@respx.mock
def test_list_medical_records_upstream_error(client):
    respx.get("http://test-main-app/api/pets/1/medical-records").mock(
        return_value=httpx.Response(500)
    )

    resp = client.get("/pets/1/medical-records", headers=_auth_headers())

    assert resp.status_code == 502
    assert resp.json()["error"] == "UPSTREAM_ERROR"
