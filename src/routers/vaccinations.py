from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.core.config import Settings, get_settings
from src.core.dependencies import get_current_token
from src.models.health import CreateVaccinationRequest, UpdateVaccinationRequest
from src.services.main_app import MainAppError, call_main_app

router = APIRouter(tags=["vaccinations"])


@router.get(
    "/pets/{pet_id}/vaccinations",
    operation_id="list_vaccinations",
    description="Retrieve all vaccination records for a pet. Requires pet_id — use find_pet first to resolve a name to an ID.",
)
async def list_vaccinations(
    pet_id: int,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current_token
    try:
        return await call_main_app(
            method="GET",
            path=f"/api/pets/{pet_id}/vaccinations",
            settings=settings,
            sanctum_token=sanctum_token,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.post(
    "/pets/{pet_id}/vaccinations",
    operation_id="add_vaccination",
    description="Record a new vaccination for a pet. When adding from a photo, extract all visible fields from the certificate before calling. Requires pet_id — use find_pet first.",
)
async def create_vaccination(
    pet_id: int,
    payload: CreateVaccinationRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current_token
    upstream: dict[str, Any] = {
        "vaccine_name": payload.vaccine_name,
        "administered_at": payload.administered_at.isoformat(),
    }
    if payload.due_at is not None:
        upstream["due_at"] = payload.due_at.isoformat()
    if payload.notes is not None:
        upstream["notes"] = payload.notes

    try:
        status_code, body = await call_main_app(
            method="POST",
            path=f"/api/pets/{pet_id}/vaccinations",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream,
            return_status=True,
        )
        return JSONResponse(status_code=status_code, content=body)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.patch(
    "/pets/{pet_id}/vaccinations/{vaccination_id}",
    operation_id="update_vaccination",
    description="Correct an existing vaccination record. Only send fields that need to change.",
)
async def update_vaccination(
    pet_id: int,
    vaccination_id: int,
    payload: UpdateVaccinationRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current_token
    upstream: dict[str, Any] = {}
    if payload.vaccine_name is not None:
        upstream["vaccine_name"] = payload.vaccine_name
    if payload.administered_at is not None:
        upstream["administered_at"] = payload.administered_at.isoformat()
    if payload.due_at is not None:
        upstream["due_at"] = payload.due_at.isoformat()
    if payload.notes is not None:
        upstream["notes"] = payload.notes

    try:
        return await call_main_app(
            method="PUT",
            path=f"/api/pets/{pet_id}/vaccinations/{vaccination_id}",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
