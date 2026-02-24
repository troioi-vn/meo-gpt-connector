from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.core.config import Settings, get_settings
from src.core.dependencies import get_current_token_limited as get_current_token
from src.models.health import (
    VALID_RECORD_TYPES,
    CreateMedicalRecordRequest,
    UpdateMedicalRecordRequest,
)
from src.services.main_app import MainAppError, call_main_app

router = APIRouter(tags=["medical-records"])


def _coerce_record_type(value: str | None) -> str:
    if value is None:
        return "other"
    return value if value in VALID_RECORD_TYPES else "other"


@router.get(
    "/pets/{pet_id}/medical-records",
    operation_id="list_medical_records",
    description="Retrieve all medical records for a pet (vet visits, deworming, treatments, surgeries, dental). Requires pet_id — use find_pet first.",
)
async def list_medical_records(
    pet_id: int,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    _, sanctum_token = current_token
    try:
        return await call_main_app(
            method="GET",
            path=f"/api/pets/{pet_id}/medical-records",
            settings=settings,
            sanctum_token=sanctum_token,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.post(
    "/pets/{pet_id}/medical-records",
    operation_id="add_medical_record",
    description="Log a new medical event for a pet. If the record_type is ambiguous, use 'other' — never invent a type. Requires pet_id — use find_pet first.",
)
async def create_medical_record(
    pet_id: int,
    payload: CreateMedicalRecordRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    _, sanctum_token = current_token
    upstream: dict[str, Any] = {
        "record_type": _coerce_record_type(payload.record_type),
    }
    if payload.description is not None:
        upstream["description"] = payload.description
    if payload.record_date is not None:
        upstream["record_date"] = payload.record_date.isoformat()
    if payload.vet_name is not None:
        upstream["vet_name"] = payload.vet_name

    try:
        status_code, body = await call_main_app(
            method="POST",
            path=f"/api/pets/{pet_id}/medical-records",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream,
            return_status=True,
        )
        return JSONResponse(status_code=status_code, content=body)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.patch(
    "/pets/{pet_id}/medical-records/{record_id}",
    operation_id="update_medical_record",
    description="Correct an existing medical record. Only send fields that need to change.",
)
async def update_medical_record(
    pet_id: int,
    record_id: int,
    payload: UpdateMedicalRecordRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
) -> Any:
    _, sanctum_token = current_token
    upstream: dict[str, Any] = {}
    if payload.record_type is not None:
        upstream["record_type"] = _coerce_record_type(payload.record_type)
    if payload.description is not None:
        upstream["description"] = payload.description
    if payload.record_date is not None:
        upstream["record_date"] = payload.record_date.isoformat()
    if payload.vet_name is not None:
        upstream["vet_name"] = payload.vet_name

    try:
        return await call_main_app(
            method="PUT",
            path=f"/api/pets/{pet_id}/medical-records/{record_id}",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
