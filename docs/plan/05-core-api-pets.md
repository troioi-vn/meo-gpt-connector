# 05 - Core API Pets (Connector)

**Goal:** Create proxy endpoints that handle GPT-friendly payloads and accurately normalize them for downstream Laravel consumption.

## Definition of Done

- `GET /pet-types` cached locally.
- `GET /pets` lists.
- `POST /pets/find` provides fuzzy matching capabilities for names, preventing hallucinations.
- `POST /pets` accepts fuzzy dates (`age_months`, `birth_month_year`) and duplicate warnings.
- Upstream HTTP errors are coerced into connector-specific JSON codes (`UPSTREAM_ERROR`, `VALIDATION_ERROR`, etc).
- Integration test for `test_pets.py`.
- Unit test for `test_normalization.py` and `test_duplicate_filter.py`.

## Implementation Steps

1. **Error Normalizer (`src/services/main_app.py`):**
   - Implement `call_main_app()` wrapper around `httpx` logic to catch 404, 422, 401, 429, 500.
   - Convert upstream error structures to standardized format:
     `{"error": "...", "message": "...", "fields": [], "request_id": "req_..."}`.
2. **`GET /pet-types`:**
   - Fetch once on startup or periodically cache all pet types from the upstream app into an internal dictionary (`{'cat': 2, 'dog': 1}`).
3. **`GET /pets` & `GET /pets/{id}`:**
   - Simply map through while enriching returning structs with precise fields.
   - Filter query parameters locally (Since `?name=` is handled locally).

4. **`POST /pets/find`:**
   - Call main app `GET /api/my-pets` with the internal `sanctum_token`.
   - Take `{ "name": "Mimi", "species": "cat" }`, lowercase exact substring match on list.
   - Return `{ "candidates": [...] }` handling both 0, 1, and N results.

5. **`POST /pets` (Create):**
   - Translate GPT's input `{"birth_date": "YYYY-MM-DD", "age_months": 6, "species": "cat"}` to `{"birthday_year": Y, "birthday_precision": "day", "pet_type_id": 2}`. Throw `VALIDATION_ERROR` if date inputs are conflicting.
   - Before hitting the main app, perform internal `POST /pets/find` logic.
   - If exact match found, block creation and return `DUPLICATE_WARNING` (HTTP 409).
   - If `confirm_duplicate: True` is passed by GPT, skip duplicate check and immediately create.
6. **`PATCH /pets/{id}`:**
   - Perform similar normalization for dates/types/sex enum (`unknown -> not_specified`), map to `PUT /api/pets/{id}` upstream.
