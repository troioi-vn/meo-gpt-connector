from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.core.config import Settings, get_settings
from src.core.dependencies import get_current_token_limited as get_current_token
from src.models.pets import (
    CreatePetRequest,
    PetFindRequest,
    PetFindResponse,
    PetSummary,
    PetTypeItem,
    UpdatePetRequest,
)
from src.services.main_app import (
    MainAppError,
    call_main_app,
    get_pet_types_by_name,
    get_species_name_by_pet_type_id,
    refresh_pet_types_cache,
)
from src.services.pets_normalization import (
    filter_pet_candidates,
    has_exact_duplicate,
    normalize_birth_fields,
    normalize_sex,
    normalize_species_to_pet_type_id,
    to_pet_summary,
)

router = APIRouter(tags=["pets"])


def _error_response(status_code: int, error: str, message: str, fields: list[dict[str, str]] | None = None, extra: dict[str, Any] | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": error,
        "message": message,
        "fields": fields or [],
        "request_id": f"req_{uuid.uuid4().hex[:12]}",
    }
    if extra:
        payload.update(extra)
    return JSONResponse(status_code=status_code, content=payload)


def _extract_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return [item for item in data["data"] if isinstance(item, dict)]
    return []


async def _load_pets(current_token: tuple[int, str], settings: Settings) -> list[dict[str, Any]]:
    _, sanctum_token = current_token
    raw = await call_main_app(
        method="GET",
        path="/api/my-pets",
        settings=settings,
        sanctum_token=sanctum_token,
    )
    species_by_type_id = get_species_name_by_pet_type_id()
    return [to_pet_summary(item, species_by_type_id) for item in _extract_list(raw)]


@router.get(
    "/pet-types",
    operation_id="list_pet_types",
    response_model=list[PetTypeItem],
    description="Retrieve all available species/pet types. Call this before create_pet if you are unsure which species names are supported.",
)
async def get_pet_types(settings: Settings = Depends(get_settings)) -> Any:
    pet_types = get_pet_types_by_name()
    if not pet_types:
        try:
            await refresh_pet_types_cache(settings)
        except MainAppError as exc:
            return JSONResponse(status_code=exc.status_code, content=exc.payload)
        pet_types = get_pet_types_by_name()

    return [PetTypeItem(id=pet_type_id, name=name) for name, pet_type_id in sorted(pet_types.items())]


@router.get(
    "/pets",
    operation_id="list_pets",
    response_model=list[PetSummary],
    description="Return all pets belonging to the authenticated user. Use find_pet instead when the user refers to a pet by name — only call list_pets when the user explicitly wants to see all their pets.",
)
async def list_pets(
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
    name: str | None = Query(default=None),
    species: str | None = Query(default=None),
) -> Any:
    try:
        pets = await _load_pets(current_token, settings)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)

    return filter_pet_candidates(pets, name=name, species=species)


@router.get(
    "/pets/{pet_id}",
    operation_id="get_pet",
    description="Retrieve full details for a single pet by its numeric ID. Requires a known pet_id — call find_pet first to resolve a name to an ID.",
)
async def get_pet(
    pet_id: int,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    _, sanctum_token = current_token
    try:
        return await call_main_app(
            method="GET",
            path=f"/api/pets/{pet_id}",
            settings=settings,
            sanctum_token=sanctum_token,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.post(
    "/pets/find",
    operation_id="find_pet",
    response_model=PetFindResponse,
    description="Search the user's pets by name and/or species. Call this BEFORE any pet-specific tool whenever the user refers to a pet by name. Use the id field from the matching candidate for all subsequent calls targeting that pet.",
)
async def find_pets(
    payload: PetFindRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    try:
        pets = await _load_pets(current_token, settings)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)

    candidates = filter_pet_candidates(pets, name=payload.name, species=payload.species)
    return PetFindResponse(candidates=[PetSummary(**item) for item in candidates])


@router.post(
    "/pets",
    operation_id="create_pet",
    description="Create a new pet profile. If the response is DUPLICATE_WARNING, do not create the pet — tell the user and ask whether this is a new animal or the same one. Only retry with confirm_duplicate=true if the user explicitly confirms it is a different animal with the same name.",
)
async def create_pet(
    payload: CreatePetRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    _, sanctum_token = current_token
    pet_types = get_pet_types_by_name()
    if not pet_types:
        try:
            await refresh_pet_types_cache(settings)
        except MainAppError as exc:
            return JSONResponse(status_code=exc.status_code, content=exc.payload)
        pet_types = get_pet_types_by_name()

    try:
        pet_type_id = normalize_species_to_pet_type_id(payload.species, pet_types)
    except ValueError as exc:
        return _error_response(
            422,
            "VALIDATION_ERROR",
            str(exc),
            fields=[{"name": "species", "reason": "unknown_species"}],
        )

    try:
        birthday_payload = normalize_birth_fields(
            birth_date=payload.birth_date,
            birth_month_year=payload.birth_month_year,
            age_months=payload.age_months,
        )
    except ValueError as exc:
        return _error_response(
            422,
            "VALIDATION_ERROR",
            str(exc),
            fields=[{"name": "birth_date", "reason": "conflicting_inputs"}],
        )

    try:
        pets = await _load_pets(current_token, settings)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)

    if not payload.confirm_duplicate and has_exact_duplicate(pets, payload.name, payload.species):
        duplicates = [
            pet for pet in pets
            if str(pet.get("name", "")).strip().lower() == payload.name.strip().lower()
        ]
        return _error_response(
            409,
            "DUPLICATE_WARNING",
            "A pet with this name already exists.",
            extra={"existing": duplicates},
        )

    upstream_payload: dict[str, Any] = {
        "name": payload.name,
        "pet_type_id": pet_type_id,
        "country": payload.country,
        "description": payload.description,
    }
    sex_value = normalize_sex(payload.sex)
    if sex_value is not None:
        upstream_payload["sex"] = sex_value
    upstream_payload.update(birthday_payload)
    upstream_payload = {key: value for key, value in upstream_payload.items() if value is not None}

    try:
        status_code, body = await call_main_app(
            method="POST",
            path="/api/pets",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream_payload,
            return_status=True,
        )
        return JSONResponse(status_code=status_code, content=body)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.patch(
    "/pets/{pet_id}",
    operation_id="update_pet",
    description="Update one or more fields on an existing pet. Only include fields the user wants to change. Requires pet_id — call find_pet first to resolve a name to an ID.",
)
async def update_pet(
    pet_id: int,
    payload: UpdatePetRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    _, sanctum_token = current_token
    upstream_payload: dict[str, Any] = {}

    if payload.name is not None:
        upstream_payload["name"] = payload.name
    if payload.description is not None:
        upstream_payload["description"] = payload.description
    if payload.sex is not None:
        upstream_payload["sex"] = normalize_sex(payload.sex)

    if payload.species is not None:
        pet_types = get_pet_types_by_name()
        if not pet_types:
            try:
                await refresh_pet_types_cache(settings)
            except MainAppError as exc:
                return JSONResponse(status_code=exc.status_code, content=exc.payload)
            pet_types = get_pet_types_by_name()

        try:
            upstream_payload["pet_type_id"] = normalize_species_to_pet_type_id(payload.species, pet_types)
        except ValueError as exc:
            return _error_response(
                422,
                "VALIDATION_ERROR",
                str(exc),
                fields=[{"name": "species", "reason": "unknown_species"}],
            )

    try:
        upstream_payload.update(
            normalize_birth_fields(
                birth_date=payload.birth_date,
                birth_month_year=payload.birth_month_year,
                age_months=payload.age_months,
            )
        )
    except ValueError as exc:
        return _error_response(
            422,
            "VALIDATION_ERROR",
            str(exc),
            fields=[{"name": "birth_date", "reason": "conflicting_inputs"}],
        )

    try:
        return await call_main_app(
            method="PUT",
            path=f"/api/pets/{pet_id}",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream_payload,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
