from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


VALID_RECORD_TYPES: frozenset[str] = frozenset(
    {"checkup", "deworming", "flea_treatment", "surgery", "dental", "other"}
)


# --- Vaccinations ---


class CreateVaccinationRequest(BaseModel):
    vaccine_name: str = Field(min_length=1, description="Name of the vaccine (e.g. 'Rabies', 'FVRCP', 'Bordetella').")
    administered_at: date = Field(description="Date the vaccine was administered (YYYY-MM-DD).")
    due_at: date | None = Field(default=None, description="Date the next dose is due (YYYY-MM-DD). Include if stated on the certificate.")
    notes: str | None = Field(default=None, description="Any extra notes from the vaccination certificate or vet.")


class UpdateVaccinationRequest(BaseModel):
    vaccine_name: str | None = Field(default=None, description="Corrected vaccine name.")
    administered_at: date | None = Field(default=None, description="Corrected administration date (YYYY-MM-DD).")
    due_at: date | None = Field(default=None, description="Corrected due date (YYYY-MM-DD).")
    notes: str | None = Field(default=None, description="Corrected notes.")


# --- Medical Records ---


class CreateMedicalRecordRequest(BaseModel):
    record_type: str = Field(
        default="other",
        description="Type of medical event. Must be one of: checkup, deworming, flea_treatment, surgery, dental, other. Default to 'other' if unsure.",
    )
    description: str | None = Field(default=None, description="Free-text description of what happened (symptoms, treatment, observations).")
    record_date: date | None = Field(default=None, description="Date of the event (YYYY-MM-DD). Omit only if truly unknown.")
    vet_name: str | None = Field(default=None, description="Name of the veterinarian or clinic, if mentioned.")


class UpdateMedicalRecordRequest(BaseModel):
    record_type: str | None = Field(default=None, description="Corrected record type (checkup, deworming, flea_treatment, surgery, dental, other).")
    description: str | None = Field(default=None, description="Corrected description.")
    record_date: date | None = Field(default=None, description="Corrected event date (YYYY-MM-DD).")
    vet_name: str | None = Field(default=None, description="Corrected vet or clinic name.")


# --- Weights ---


class CreateWeightRequest(BaseModel):
    weight_kg: float = Field(gt=0, le=1000, description="Body weight in kilograms. Convert from grams if needed (divide by 1000).")
    measured_at: date | None = Field(default=None, description="Date the weight was measured (YYYY-MM-DD). Defaults to today if omitted.")


class UpdateWeightRequest(BaseModel):
    weight_kg: float | None = Field(default=None, gt=0, le=1000, description="Corrected weight in kilograms.")
    measured_at: date | None = Field(default=None, description="Corrected measurement date (YYYY-MM-DD).")
