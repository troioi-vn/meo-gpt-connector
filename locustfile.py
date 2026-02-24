"""Meo GPT Connector — load test via Locust.

Usage:
    # Install: uv pip install locust  (or: pip install locust)
    # Provide a valid JWT (obtained from a real OAuth flow):
    export MEO_TEST_JWT="eyJ..."
    locust -f locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 60s

What this confirms:
    - /health stays fast and returns 200 under concurrent /pets traffic
    - Rate limiter blocks bursts (look for 429s in the report)
    - uvicorn does not crash under sustained load
"""

import os

from locust import HttpUser, between, task


class PetsUser(HttpUser):
    """Simulates an authenticated GPT action caller."""

    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        jwt = os.environ.get("MEO_TEST_JWT", "")
        if not jwt:
            raise ValueError("Set MEO_TEST_JWT env var to a valid connector JWT before running")
        self.auth_headers = {"Authorization": f"Bearer {jwt}"}

    @task(5)
    def list_pets(self) -> None:
        self.client.get("/pets", headers=self.auth_headers, name="/pets")

    @task(2)
    def find_pet(self) -> None:
        self.client.post(
            "/pets/find",
            json={"name": "test"},
            headers=self.auth_headers,
            name="/pets/find",
        )

    @task(1)
    def health_check(self) -> None:
        """Health endpoint must stay fast regardless of /pets traffic."""
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Health check returned {resp.status_code}")
