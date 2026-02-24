import httpx
import respx

from src.core.jwt import create_jwt


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id=9, sanctum_token='sanctum-token')}"}


@respx.mock
def test_list_vaccinations(client):
    respx.get("http://test-main-app/api/pets/1/vaccinations").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 10, "vaccine_name": "Rabies", "administered_at": "2024-06-01"}],
        )
    )

    resp = client.get("/pets/1/vaccinations", headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["vaccine_name"] == "Rabies"


@respx.mock
def test_create_vaccination(client):
    route = respx.post("http://test-main-app/api/pets/1/vaccinations").mock(
        return_value=httpx.Response(
            201,
            json={"id": 11, "vaccine_name": "FVRCP", "administered_at": "2024-06-15"},
        )
    )

    resp = client.post(
        "/pets/1/vaccinations",
        json={"vaccine_name": "FVRCP", "administered_at": "2024-06-15"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    assert resp.json()["vaccine_name"] == "FVRCP"
    assert route.called
    sent = route.calls[0].request
    import json
    body = json.loads(sent.content)
    assert body["administered_at"] == "2024-06-15"
    assert "due_at" not in body


@respx.mock
def test_create_vaccination_with_optional_fields(client):
    route = respx.post("http://test-main-app/api/pets/1/vaccinations").mock(
        return_value=httpx.Response(201, json={"id": 12})
    )

    resp = client.post(
        "/pets/1/vaccinations",
        json={
            "vaccine_name": "Bordetella",
            "administered_at": "2024-07-01",
            "due_at": "2025-07-01",
            "notes": "Annual booster",
        },
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    import json
    body = json.loads(route.calls[0].request.content)
    assert body["due_at"] == "2025-07-01"
    assert body["notes"] == "Annual booster"


@respx.mock
def test_update_vaccination(client):
    route = respx.put("http://test-main-app/api/pets/1/vaccinations/10").mock(
        return_value=httpx.Response(
            200,
            json={"id": 10, "vaccine_name": "Rabies", "due_at": "2025-06-01"},
        )
    )

    resp = client.patch(
        "/pets/1/vaccinations/10",
        json={"due_at": "2025-06-01"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    assert resp.json()["due_at"] == "2025-06-01"
    assert route.called
    import json
    body = json.loads(route.calls[0].request.content)
    assert body == {"due_at": "2025-06-01"}


@respx.mock
def test_create_vaccination_missing_required_field(client):
    resp = client.post(
        "/pets/1/vaccinations",
        json={"vaccine_name": "Rabies"},  # missing administered_at
        headers=_auth_headers(),
    )

    assert resp.status_code == 422


@respx.mock
def test_list_vaccinations_upstream_404(client):
    respx.get("http://test-main-app/api/pets/999/vaccinations").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )

    resp = client.get("/pets/999/vaccinations", headers=_auth_headers())

    assert resp.status_code == 404
    assert resp.json()["error"] == "NOT_FOUND"
