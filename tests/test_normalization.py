from datetime import date

import pytest

from src.services.pets_normalization import normalize_birth_fields, normalize_sex, normalize_species_to_pet_type_id


def test_normalize_species_to_pet_type_id_success():
    mapping = {"cat": 2, "dog": 1}
    assert normalize_species_to_pet_type_id("Cat", mapping) == 2


def test_normalize_species_to_pet_type_id_unknown():
    mapping = {"cat": 2}
    with pytest.raises(ValueError):
        normalize_species_to_pet_type_id("hamster", mapping)


def test_normalize_birth_fields_from_birth_date():
    value = normalize_birth_fields(
        birth_date=date(2023, 7, 14),
        birth_month_year=None,
        age_months=None,
    )
    assert value == {
        "birthday_year": 2023,
        "birthday_month": 7,
        "birthday_day": 14,
        "birthday_precision": "day",
    }


def test_normalize_birth_fields_from_birth_month_year():
    value = normalize_birth_fields(
        birth_date=None,
        birth_month_year="2024-02",
        age_months=None,
    )
    assert value == {
        "birthday_year": 2024,
        "birthday_month": 2,
        "birthday_precision": "month",
    }


def test_normalize_birth_fields_from_age_months():
    value = normalize_birth_fields(
        birth_date=None,
        birth_month_year=None,
        age_months=6,
        today=date(2026, 2, 23),
    )
    assert value == {
        "birthday_year": 2025,
        "birthday_month": 8,
        "birthday_precision": "month",
    }


def test_normalize_birth_fields_reject_conflicting_inputs():
    with pytest.raises(ValueError):
        normalize_birth_fields(
            birth_date=date(2024, 1, 1),
            birth_month_year="2024-01",
            age_months=None,
        )


def test_normalize_sex_maps_unknown():
    assert normalize_sex("unknown") == "not_specified"
    assert normalize_sex("female") == "female"
