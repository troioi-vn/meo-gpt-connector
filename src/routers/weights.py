from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.core.config import Settings, get_settings
from src.core.dependencies import get_current_token
from src.models.health import CreateWeightRequest, UpdateWeightRequest
from src.services.main_app import MainAppError, call_main_app

router = APIRouter(tags=["weights"])


@router.get("/pets/{pet_id}/weights")
async def list_weights(
    pet_id: int,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current_token
    try:
        return await call_main_app(
            method="GET",
            path=f"/api/pets/{pet_id}/weights",
            settings=settings,
            sanctum_token=sanctum_token,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.post("/pets/{pet_id}/weights")
async def create_weight(
    pet_id: int,
    payload: CreateWeightRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current_token
    record_date = payload.measured_at if payload.measured_at is not None else date.today()
    upstream: dict[str, Any] = {
        "weight_kg": payload.weight_kg,
        "record_date": record_date.isoformat(),
    }

    try:
        status_code, body = await call_main_app(
            method="POST",
            path=f"/api/pets/{pet_id}/weights",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream,
            return_status=True,
        )
        return JSONResponse(status_code=status_code, content=body)
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.patch("/pets/{pet_id}/weights/{weight_id}")
async def update_weight(
    pet_id: int,
    weight_id: int,
    payload: UpdateWeightRequest,
    current_token: Annotated[tuple[int, str], Depends(get_current_token)],
    settings: Settings = Depends(get_settings),
):
    _, sanctum_token = current_token
    upstream: dict[str, Any] = {}
    if payload.weight_kg is not None:
        upstream["weight_kg"] = payload.weight_kg
    if payload.measured_at is not None:
        upstream["record_date"] = payload.measured_at.isoformat()

    try:
        return await call_main_app(
            method="PUT",
            path=f"/api/pets/{pet_id}/weights/{weight_id}",
            settings=settings,
            sanctum_token=sanctum_token,
            json_data=upstream,
        )
    except MainAppError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
