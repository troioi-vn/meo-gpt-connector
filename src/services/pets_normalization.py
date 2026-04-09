from __future__ import annotations

from datetime import date
from typing import Any


_BIRTHDAY_PRECISIONS = {"day", "month", "year", "unknown"}


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_birthday_precision(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in _BIRTHDAY_PRECISIONS:
        return normalized
    return None


def _format_age_from_birthdate(birthdate: date, *, today: date) -> str | None:
    if birthdate > today:
        return None

    years = today.year - birthdate.year
    months = today.month - birthdate.month
    if today.day < birthdate.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    parts: list[str] = []
    if years > 0:
        parts.append(f"{years} year" if years == 1 else f"{years} years")
    if months > 0:
        parts.append(f"{months} month" if months == 1 else f"{months} months")

    if not parts:
        return "less than 1 month"
    return " ".join(parts)


def _build_birthday_date(year: int | None, month: int | None, day: int | None) -> date | None:
    if year is None or month is None or day is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def build_pet_time_context(raw: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    ref = today or date.today()
    precision = _normalize_birthday_precision(raw.get("birthday_precision"))
    birthday_year = _coerce_int(raw.get("birthday_year"))
    birthday_month = _coerce_int(raw.get("birthday_month"))
    birthday_day = _coerce_int(raw.get("birthday_day"))

    age = raw.get("age")
    if not isinstance(age, str) or not age.strip():
        age = None

    if age is None and precision == "day":
        birthdate = _build_birthday_date(birthday_year, birthday_month, birthday_day)
        if birthdate is not None:
            age = _format_age_from_birthdate(birthdate, today=ref)

    next_birthday_at: date | None = None
    days_until_next_birthday: int | None = None
    if precision == "day" and birthday_month is not None and birthday_day is not None:
        for candidate_year in (ref.year, ref.year + 1):
            try:
                candidate = date(candidate_year, birthday_month, birthday_day)
            except ValueError:
                continue
            if candidate >= ref:
                next_birthday_at = candidate
                days_until_next_birthday = (candidate - ref).days
                break

    return {
        "age": age,
        "birthday_precision": precision,
        "birthday_year": birthday_year,
        "birthday_month": birthday_month,
        "birthday_day": birthday_day,
        "next_birthday_at": next_birthday_at,
        "days_until_next_birthday": days_until_next_birthday,
    }


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
        y_str, m_str = birth_month_year.split("-")
        return {
            "birthday_year": int(y_str),
            "birthday_month": int(m_str),
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


def to_pet_summary(
    raw: dict[str, Any],
    species_by_type_id: dict[int, str],
    *,
    today: date | None = None,
) -> dict[str, Any]:
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
        "photo_url": raw.get("photo_url"),
        **build_pet_time_context(raw, today=today),
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
