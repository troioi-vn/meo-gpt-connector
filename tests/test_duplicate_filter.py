from src.services.pets_normalization import filter_pet_candidates, has_exact_duplicate


PETS = [
    {"id": 1, "name": "Mimi", "species": "cat"},
    {"id": 2, "name": "Milo", "species": "dog"},
    {"id": 3, "name": "Mi", "species": "cat"},
]


def test_filter_pet_candidates_name_substring_case_insensitive():
    result = filter_pet_candidates(PETS, name="mi")
    assert [item["id"] for item in result] == [3, 2, 1]


def test_filter_pet_candidates_species_narrowing():
    result = filter_pet_candidates(PETS, name="mi", species="cat")
    assert [item["id"] for item in result] == [3, 1]


def test_filter_pet_candidates_zero_results():
    result = filter_pet_candidates(PETS, name="zzz")
    assert result == []


def test_has_exact_duplicate_true():
    assert has_exact_duplicate(PETS, name="mimi", species="cat") is True


def test_has_exact_duplicate_false():
    assert has_exact_duplicate(PETS, name="mimi", species="dog") is False
