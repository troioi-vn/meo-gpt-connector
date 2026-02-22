from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


SexInput = Literal["male", "female", "unknown", "not_specified"]


class PetTypeItem(BaseModel):
    id: int
    name: str


class PetSummary(BaseModel):
    id: int
    name: str
    species: str | None = None
    sex: str | None = None
    age: str | None = None
    photo_url: str | None = None


class PetFindRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    species: str | None = Field(default=None, min_length=1)


class PetFindResponse(BaseModel):
    candidates: list[PetSummary]


class CreatePetRequest(BaseModel):
    name: str = Field(min_length=1)
    species: str = Field(min_length=1)
    sex: SexInput | None = None
    birth_date: date | None = None
    birth_month_year: str | None = None
    age_months: int | None = Field(default=None, ge=0, le=600)
    description: str | None = None
    confirm_duplicate: bool = False

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
    pet: dict


class UpdatePetRequest(BaseModel):
    name: str | None = None
    species: str | None = None
    sex: SexInput | None = None
    birth_date: date | None = None
    birth_month_year: str | None = None
    age_months: int | None = Field(default=None, ge=0, le=600)
    description: str | None = None

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
