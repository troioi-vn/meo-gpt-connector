import httpx
import respx

from src.core.jwt import create_jwt


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id=9, sanctum_token='sanctum-token')}"}


@respx.mock
def test_get_pet_types_cached_lookup(client):
    respx.get("http://test-main-app/api/pet-types").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "name": "cat"}, {"id": 1, "name": "dog"}])
    )

    resp = client.get("/pet-types")

    assert resp.status_code == 200
    assert resp.json() == [{"id": 2, "name": "cat"}, {"id": 1, "name": "dog"}]


@respx.mock
def test_list_pets_filters_by_name(client):
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Mimi", "pet_type_id": 2, "sex": "female"},
                {"id": 2, "name": "Bun", "pet_type_id": 1, "sex": "male"},
            ],
        )
    )

    resp = client.get("/pets", params={"name": "mi"}, headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Mimi"


@respx.mock
def test_find_pets_returns_multiple_candidates(client):
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Mimi", "pet_type_id": 2},
                {"id": 2, "name": "Mimo", "pet_type_id": 2},
            ],
        )
    )

    resp = client.post("/pets/find", json={"name": "mi"}, headers=_auth_headers())

    assert resp.status_code == 200
    assert len(resp.json()["candidates"]) == 2


@respx.mock
def test_create_pet_duplicate_warning(client):
    respx.get("http://test-main-app/api/pet-types").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "name": "cat"}])
    )
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Mimi", "pet_type_id": 2}])
    )

    resp = client.post(
        "/pets",
        json={"name": "Mimi", "species": "cat", "sex": "unknown", "age_months": 6},
        headers=_auth_headers(),
    )

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "DUPLICATE_WARNING"
    assert body["existing"][0]["name"] == "Mimi"


@respx.mock
def test_create_pet_confirm_duplicate_skips_block(client):
    respx.get("http://test-main-app/api/pet-types").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "name": "cat"}])
    )
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Mimi", "pet_type_id": 2}])
    )
    create_route = respx.post("http://test-main-app/api/pets").mock(
        return_value=httpx.Response(201, json={"id": 5, "name": "Mimi 2"})
    )

    resp = client.post(
        "/pets",
        json={"name": "Mimi", "species": "cat", "confirm_duplicate": True, "birth_month_year": "2025-01"},
        headers=_auth_headers(),
    )

    assert resp.status_code == 201
    assert resp.json()["id"] == 5
    assert create_route.called


@respx.mock
def test_upstream_422_is_normalized(client):
    respx.get("http://test-main-app/api/my-pets").mock(
        return_value=httpx.Response(422, json={"message": "Invalid", "errors": {"name": ["Required"]}})
    )

    resp = client.get("/pets", headers=_auth_headers())

    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert data["fields"][0]["name"] == "name"
