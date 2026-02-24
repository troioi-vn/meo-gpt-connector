#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx

from src.core.jwt import create_jwt


def _extract_pet_id(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("data"), dict) and payload["data"].get("id"):
        return int(payload["data"]["id"])
    if payload.get("id"):
        return int(payload["id"])
    if isinstance(payload.get("pet"), dict) and payload["pet"].get("id"):
        return int(payload["pet"]["id"])
    return None


def _seed_pet_in_main_app(main_app_base: str, sanctum_token: str, name: str) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {sanctum_token}", "Accept": "application/json"}
    with httpx.Client(base_url=main_app_base, headers=headers, timeout=20.0) as client:
        pet_types_resp = client.get("/api/pet-types")
        pet_types_resp.raise_for_status()
        pet_types_data = pet_types_resp.json()
        items = pet_types_data.get("data", []) if isinstance(pet_types_data, dict) else pet_types_data
        cat = next((x for x in items if isinstance(x, dict) and str(x.get("name", "")).lower() == "cat"), None)
        pet_type_id = int(cat["id"]) if cat and cat.get("id") is not None else None

        payload = {
            "name": name,
            "country": "VN",
            "pet_type_id": pet_type_id,
            "sex": "female",
            "description": "Seeded for GPT connector simulation",
            "birthday_precision": "month",
            "birthday_year": 2025,
            "birthday_month": 1,
        }
        create_resp = client.post("/api/pets", json=payload)
        create_resp.raise_for_status()
        body = create_resp.json()
        pet_id = _extract_pet_id(body)
        if pet_id is None:
            raise RuntimeError("Could not parse pet_id from main app seed response")
        return pet_id, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate how GPT uses connector tools after auth.")
    parser.add_argument("--sanctum-token", required=True, help="Main app Sanctum token (plain text form, e.g. 1|...).")
    parser.add_argument("--user-id", required=True, type=int, help="User ID tied to the Sanctum token.")
    parser.add_argument("--connector-base", default="http://localhost:8001", help="Connector base URL.")
    parser.add_argument("--main-app-base", default="http://localhost:8000", help="Main app base URL.")
    parser.add_argument("--pet-name", default=None, help="Optional fixed pet name for simulation.")
    args = parser.parse_args()

    pet_name = args.pet_name or f"GPT Sim {int(time.time())}"
    connector_base = args.connector_base.rstrip("/")
    main_app_base = args.main_app_base.rstrip("/")

    token = create_jwt(args.user_id, args.sanctum_token)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    summary: dict[str, Any] = {
        "pet_name": pet_name,
        "connector_base": connector_base,
        "main_app_base": main_app_base,
        "steps": [],
    }

    with httpx.Client(base_url=connector_base, headers=headers, timeout=25.0) as client:
        create_payload = {
            "name": pet_name,
            "species": "cat",
            "sex": "female",
            "age_months": 14,
            "description": "Created by GPT simulation",
        }
        create_resp = client.post("/pets", json=create_payload)
        create_body = create_resp.json() if create_resp.content else {}
        summary["steps"].append({"step": "connector_create_pet", "status": create_resp.status_code, "body": create_body})

        pet_id = _extract_pet_id(create_body)
        if pet_id is None:
            pet_id, seed_body = _seed_pet_in_main_app(main_app_base, args.sanctum_token, pet_name)
            summary["steps"].append({"step": "main_app_seed_pet", "status": 201, "body": seed_body})

        find_resp = client.post("/pets/find", json={"name": pet_name, "species": "cat"})
        summary["steps"].append({"step": "connector_find_pet", "status": find_resp.status_code, "body": find_resp.json()})

        update_resp = client.patch(f"/pets/{pet_id}", json={"description": "Updated by GPT simulation"})
        summary["steps"].append({"step": "connector_update_pet", "status": update_resp.status_code, "body": update_resp.json()})

        weight_resp = client.post(
            f"/pets/{pet_id}/weights",
            json={"weight_kg": 3.4, "measured_at": "2026-02-25"},
        )
        summary["steps"].append({"step": "connector_add_weight", "status": weight_resp.status_code, "body": weight_resp.json()})

        vacc_resp = client.post(
            f"/pets/{pet_id}/vaccinations",
            json={
                "vaccine_name": "Rabies",
                "administered_at": "2026-02-20",
                "due_at": "2027-02-20",
                "notes": "GPT simulation",
            },
        )
        summary["steps"].append({"step": "connector_add_vaccination", "status": vacc_resp.status_code, "body": vacc_resp.json()})

        medical_resp = client.post(
            f"/pets/{pet_id}/medical-records",
            json={
                "record_type": "checkup",
                "description": "Routine check by GPT simulation",
                "record_date": "2026-02-24",
                "vet_name": "Dr. Meo",
            },
        )
        summary["steps"].append({"step": "connector_add_medical_record", "status": medical_resp.status_code, "body": medical_resp.json()})

        list_weights = client.get(f"/pets/{pet_id}/weights")
        list_vaccinations = client.get(f"/pets/{pet_id}/vaccinations")
        list_medical = client.get(f"/pets/{pet_id}/medical-records")
        summary["steps"].append({"step": "connector_list_weights", "status": list_weights.status_code})
        summary["steps"].append({"step": "connector_list_vaccinations", "status": list_vaccinations.status_code})
        summary["steps"].append({"step": "connector_list_medical_records", "status": list_medical.status_code})

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    failed = [s for s in summary["steps"] if s.get("status", 500) >= 400 and s["step"] != "connector_create_pet"]
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
