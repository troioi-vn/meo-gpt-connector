from __future__ import annotations

from datetime import date
from typing import Any


def normalize_species_to_pet_type_id(species: str, pet_types_by_name: dict[str, int]) -> int:
    normalized = species.strip().lower()
    pet_type_id = pet_types_by_name.get(normalized)
    if pet_type_id is None:
        raise ValueError(f"Unknown species: {species}")
    return pet_type_id


def normalize_sex(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "unknown":
        return "not_specified"
    return value


def normalize_birth_fields(
    *,
    birth_date: date | None,
    birth_month_year: str | None,
    age_months: int | None,
    today: date | None = None,
) -> dict[str, Any]:
    count = int(birth_date is not None) + int(birth_month_year is not None) + int(age_months is not None)
    if count > 1:
        raise ValueError("Only one of birth_date, birth_month_year, age_months can be provided")

    if birth_date is not None:
        return {
            "birthday_year": birth_date.year,
            "birthday_month": birth_date.month,
            "birthday_day": birth_date.day,
            "birthday_precision": "day",
        }

    if birth_month_year is not None:
        year, month = birth_month_year.split("-")
        return {
            "birthday_year": int(year),
            "birthday_month": int(month),
            "birthday_precision": "month",
        }

    if age_months is not None:
        ref = today or date.today()
        absolute_month = ref.year * 12 + (ref.month - 1) - age_months
        if absolute_month < 0:
            raise ValueError("age_months is out of valid range")
        year = absolute_month // 12
        month = absolute_month % 12 + 1
        return {
            "birthday_year": year,
            "birthday_month": month,
            "birthday_precision": "month",
        }

    return {}


def to_pet_summary(raw: dict[str, Any], species_by_type_id: dict[int, str]) -> dict[str, Any]:
    pet_type_id = raw.get("pet_type_id")
    species = None
    try:
        if pet_type_id is not None:
            species = species_by_type_id.get(int(pet_type_id))
    except (TypeError, ValueError):
        species = None

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "species": species,
        "sex": raw.get("sex"),
        "age": raw.get("age"),
        "photo_url": raw.get("photo_url"),
    }


def filter_pet_candidates(pets: list[dict[str, Any]], name: str | None = None, species: str | None = None) -> list[dict[str, Any]]:
    filtered = pets

    if species:
        species_lower = species.strip().lower()
        filtered = [
            pet for pet in filtered
            if isinstance(pet.get("species"), str) and pet["species"].strip().lower() == species_lower
        ]

    if name:
        name_lower = name.strip().lower()
        filtered = [
            pet for pet in filtered
            if isinstance(pet.get("name"), str) and name_lower in pet["name"].strip().lower()
        ]

        filtered.sort(
            key=lambda pet: (
                0 if pet.get("name", "").strip().lower() == name_lower else 1,
                pet.get("name", "").strip().lower(),
            )
        )

    return filtered


def has_exact_duplicate(candidates: list[dict[str, Any]], name: str, species: str | None = None) -> bool:
    name_lower = name.strip().lower()
    species_lower = species.strip().lower() if species else None

    for candidate in candidates:
        candidate_name = str(candidate.get("name", "")).strip().lower()
        if candidate_name != name_lower:
            continue
        if species_lower is None:
            return True
        candidate_species = str(candidate.get("species", "")).strip().lower()
        if candidate_species == species_lower:
            return True
    return False
