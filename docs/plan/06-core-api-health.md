# 06 - Core API Health Records

**Goal:** Create proxy endpoints for vaccinations, medical records, and weight logging.

## Definition of Done

- CRUD operations for `vaccinations`, `medical-records`, and `weights`.
- Enum fallbacks (e.g. unknown `record_type` falls to `"other"`).
- Integration tests confirming End-to-End lifecycle mapping.

## Implementation Steps

1. **Vaccination Endpoints (`src/routers/vaccinations.py`):**
   - **`GET /pets/{id}/vaccinations`**: Proxy downstream.
   - **`POST /pets/{id}/vaccinations`**: Takes `{ vaccine_name, administered_at, due_at, notes }`. Ensures correct translation.
   - **`PATCH /pets/{id}/vaccinations/{vid}`**: Maps to `PUT` upstream.
2. **Medical Record Endpoints (`src/routers/medical_records.py`):**
   - **`GET /pets/{id}/medical-records`**: Proxy downstream.
   - **`POST /pets/{id}/medical-records`**: Accepts `{ record_type, description, record_date, vet_name }`. Enforce `record_type` string literals (`checkup, deworming, flea_treatment, surgery, dental, other`). Default to `"other"` instead of crashing.
   - **`PATCH /pets/{id}/medical-records/{rid}`**: Map to `PUT`.
3. **Weight Endpoints (`src/routers/weights.py`):**
   - **`GET /pets/{id}/weights`**: Proxy.
   - **`POST /pets/{id}/weights`**: Accept `{ weight_kg, measured_at }`. Map `measured_at` -> `record_date` downstream. No specific bulk point needed (handled by GPT orchestrating the loop).
4. **Integration Tests (`tests/integration/`):**
   - `test_vaccinations.py`: Standard CRUD loops.
   - `test_medical_records.py`: Confirm `mystery_type` gracefully degrades to `"other"`.
   - `test_weights.py`: Post valid/invalid float boundaries.
