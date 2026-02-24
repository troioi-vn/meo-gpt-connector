from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


VALID_RECORD_TYPES: frozenset[str] = frozenset(
    {"checkup", "deworming", "flea_treatment", "surgery", "dental", "other"}
)


# --- Vaccinations ---


class CreateVaccinationRequest(BaseModel):
    vaccine_name: str = Field(min_length=1)
    administered_at: date
    due_at: date | None = None
    notes: str | None = None


class UpdateVaccinationRequest(BaseModel):
    vaccine_name: str | None = None
    administered_at: date | None = None
    due_at: date | None = None
    notes: str | None = None


# --- Medical Records ---


class CreateMedicalRecordRequest(BaseModel):
    record_type: str = Field(default="other")
    description: str | None = None
    record_date: date | None = None
    vet_name: str | None = None


class UpdateMedicalRecordRequest(BaseModel):
    record_type: str | None = None
    description: str | None = None
    record_date: date | None = None
    vet_name: str | None = None


# --- Weights ---


class CreateWeightRequest(BaseModel):
    weight_kg: float = Field(gt=0, le=1000)
    measured_at: date | None = None  # maps to record_date downstream; defaults to today


class UpdateWeightRequest(BaseModel):
    weight_kg: float | None = Field(default=None, gt=0, le=1000)
    measured_at: date | None = None  # maps to record_date downstream
