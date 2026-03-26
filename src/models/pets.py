from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SexInput = Literal["male", "female", "unknown", "not_specified"]
BirthdayPrecision = Literal["day", "month", "year", "unknown"]
DataStatus = Literal["available", "unavailable"]


class PetTypeItem(BaseModel):
    id: int = Field(description="Numeric pet type ID used by the main app.")
    name: str = Field(description="Human-readable species name (e.g. 'cat', 'dog').")


class PetSummary(BaseModel):
    id: int = Field(description="Pet's unique numeric ID. Use this ID for all subsequent calls targeting this pet.")
    name: str = Field(description="Pet's name.")
    species: str | None = Field(default=None, description="Species name (e.g. 'cat', 'dog'). Use to disambiguate when multiple pets share a name.")
    sex: str | None = Field(default=None, description="'male', 'female', or 'unknown'.")
    age: str | None = Field(default=None, description="Human-readable approximate age string.")
    photo_url: str | None = Field(default=None, description="URL of the pet's profile photo, if available.")


class PetFindRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, description="Pet name to search for. Case-insensitive partial match.")
    species: str | None = Field(default=None, min_length=1, description="Optional species filter (e.g. 'cat', 'dog').")


class PetFindResponse(BaseModel):
    candidates: list[PetSummary] = Field(description="Matched pets. If 1 result: use it. If 0: tell user no pet was found. If multiple: list them and ask the user to choose.")


class PetsOverviewRequest(BaseModel):
    species: str | None = Field(
        default=None,
        min_length=1,
        description="Optional species filter (e.g. 'cat', 'dog'). Use this when the user asks about only one species.",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        description="Optional partial pet-name filter (case-insensitive).",
    )
    only_with_upcoming_vaccination: bool = Field(
        default=False,
        description="Set true when the user asks for pets that have an upcoming vaccination date.",
    )
    sort_by: Literal["name", "next_vaccination_due_at", "next_birthday_at"] = Field(
        default="name",
        description="Sort field. Use next_vaccination_due_at for care due-date questions, or next_birthday_at when the user asks whose birthday is next.",
    )
    sort_order: Literal["asc", "desc"] = Field(
        default="asc",
        description="Sort order. Use asc for soonest due first, desc for latest due first.",
    )


class PetOverviewItem(PetSummary):
    active_vaccinations: list["PetOverviewVaccinationItem"] = Field(
        default_factory=list,
        description="Active vaccination records for this pet (completed records are excluded).",
    )
    recent_weights: list["PetOverviewWeightItem"] = Field(
        default_factory=list,
        description="Up to 5 most recent weight records, newest first.",
    )
    birthday_precision: BirthdayPrecision | None = Field(
        default=None,
        description="Birthday accuracy from the main app. 'day' means exact date, 'month' means month/year only, 'year' means year only, 'unknown' means no birthday data.",
    )
    birthday_year: int | None = Field(
        default=None,
        description="Recorded birth year, if available.",
    )
    birthday_month: int | None = Field(
        default=None,
        description="Recorded birth month, if available.",
    )
    birthday_day: int | None = Field(
        default=None,
        description="Recorded birth day of month, if available.",
    )
    next_birthday_at: date | None = Field(
        default=None,
        description="Next upcoming birthday date when the pet has an exact month and day. Null when the birthday is only approximate or unknown.",
    )
    days_until_next_birthday: int | None = Field(
        default=None,
        description="Number of whole days until next_birthday_at. Null when the next birthday date cannot be computed exactly.",
    )
    next_vaccination_due_at: date | None = Field(
        default=None,
        description="Earliest vaccination due date that is today or in the future. Null if unavailable.",
    )
    next_vaccination_name: str | None = Field(
        default=None,
        description="Vaccine name for next_vaccination_due_at, if available.",
    )
    vaccination_data_status: DataStatus = Field(
        description="Whether vaccination history was successfully loaded for this pet.",
    )
    weights_data_status: DataStatus = Field(
        description="Whether weight history was successfully loaded for this pet.",
    )


class PetOverviewVaccinationItem(BaseModel):
    id: int | None = Field(default=None, description="Vaccination record ID, if available.")
    vaccine_name: str | None = Field(default=None, description="Name of the vaccine.")
    administered_at: date | None = Field(default=None, description="Date the vaccine was administered (YYYY-MM-DD).")
    due_at: date | None = Field(default=None, description="Date the next dose is due (YYYY-MM-DD), if present.")


class PetOverviewWeightItem(BaseModel):
    id: int | None = Field(default=None, description="Weight record ID, if available.")
    weight_kg: float | None = Field(default=None, description="Recorded body weight in kilograms.")
    record_date: date | None = Field(default=None, description="Date the weight was recorded (YYYY-MM-DD).")


class CreatePetRequest(BaseModel):
    name: str = Field(min_length=1, description="Pet's name exactly as the user stated it.")
    species: str = Field(min_length=1, description="Species in plain text (e.g. 'cat', 'dog', 'rabbit'). Will be mapped to an internal ID.")
    sex: SexInput | None = Field(default=None, description="Use 'unknown' if the user did not mention sex. Omit only if truly not mentioned.")
    birth_date: date | None = Field(default=None, description="Exact birth date (YYYY-MM-DD). Use only when the exact full date is known.")
    birth_month_year: str | None = Field(default=None, description="Approximate birth month in YYYY-MM format. Use when only year and month are known.")
    age_months: int | None = Field(default=None, ge=0, le=600, description="Approximate age in whole months. Use as a last resort when no date is available.")
    country: str | None = Field(default=None, min_length=2, max_length=2, description="2-letter ISO 3166-1 alpha-2 country code where the pet lives (e.g. 'VN', 'US', 'DE'). Required by the system — ask the user if not known from context.")
    description: str | None = Field(default=None, description="Optional free-text notes about the pet.")
    confirm_duplicate: bool = Field(default=False, description="Set to true only after the user explicitly confirms this is a new pet despite a DUPLICATE_WARNING response.")

    @field_validator("birth_month_year")
    @classmethod
    def validate_birth_month_year(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError("birth_month_year must be in YYYY-MM format")
        year, month = parts
        if len(year) != 4 or len(month) != 2:
            raise ValueError("birth_month_year must be in YYYY-MM format")
        if not year.isdigit() or not month.isdigit():
            raise ValueError("birth_month_year must be in YYYY-MM format")
        month_number = int(month)
        if month_number < 1 or month_number > 12:
            raise ValueError("birth_month_year month must be between 01 and 12")
        return value


class PetUpsertResponse(BaseModel):
    pet: dict[str, Any]


class UpdatePetRequest(BaseModel):
    name: str | None = Field(default=None, description="New name for the pet.")
    species: str | None = Field(default=None, description="New species if the current one was recorded incorrectly.")
    sex: SexInput | None = Field(default=None, description="Corrected sex value.")
    birth_date: date | None = Field(default=None, description="Corrected exact birth date (YYYY-MM-DD).")
    birth_month_year: str | None = Field(default=None, description="Corrected approximate birth month in YYYY-MM format.")
    age_months: int | None = Field(default=None, ge=0, le=600, description="Corrected approximate age in whole months.")
    description: str | None = Field(default=None, description="Updated description.")

    @field_validator("birth_month_year")
    @classmethod
    def validate_birth_month_year(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError("birth_month_year must be in YYYY-MM format")
        year, month = parts
        if len(year) != 4 or len(month) != 2:
            raise ValueError("birth_month_year must be in YYYY-MM format")
        if not year.isdigit() or not month.isdigit():
            raise ValueError("birth_month_year must be in YYYY-MM format")
        month_number = int(month)
        if month_number < 1 or month_number > 12:
            raise ValueError("birth_month_year month must be between 01 and 12")
        return value
