# Status Index & Agent Instructions

This directory contains the granular, step-by-step implementation plan for the `meo-gpt-connector` project, derived from our master architecture (`docs/plan-v1.1.md`).

## How to use this folder (For Agents)

When you are asked to "implement the next task in the plan", you should:

1. Examine this `index.md` file to find the first task marked as `todo`.
2. Open that specific file (e.g., `01-setup-project.md`) to read its specific, isolated context and implementation instructions.
3. Review any other relevant codebase files mentioned in that task.
4. Complete the implementation, tests, and verifications as described.
5. Once your task is successfully tested and finished, **update this `index.md` file** by changing the task's status from `todo` to `done`.

## Task Statuses

| #   | Status | File                                             | Description                                                                 |
| --- | ------ | ------------------------------------------------ | --------------------------------------------------------------------------- |
| 01  | done   | [01-setup-project.md](./01-setup-project.md)     | Init FastAPI, Docker, configuration, logging, health check, basic CI tests  |
| 02  | done   | [02-auth-utils.md](./02-auth-utils.md)           | Redis client setup, JWT utilities, Sanctum token AES encryption             |
| 03  | done   | [03-oauth-endpoints.md](./03-oauth-endpoints.md) | OAuth2 endpoints (/authorize, /callback, /token, /revoke) & Auth Middleware |
| 04  | done   | [04-main-app-auth.md](./04-main-app-auth.md)     | Implement `/gpt-connect` React page & `/api/gpt-auth/*` API in main app     |
| 05  | todo   | [05-core-api-pets.md](./05-core-api-pets.md)     | Pet endpoints: GET, POST, translation schemas, semantic search              |
| 06  | todo   | [06-core-api-health.md](./06-core-api-health.md) | Vaccination, medical record, and weight endpoints                           |
| 07  | todo   | [07-admin-interface.md](./07-admin-interface.md) | Minimal developer dashboard via HDMX and Jinja, Redis event logging         |
| 08  | todo   | [08-gpt-integration.md](./08-gpt-integration.md) | OpenAPI descriptions, System Prompts, OpenAI configuration                  |
| 09  | todo   | [09-hardening.md](./09-hardening.md)             | Rate Limiting, Idempotency Guards, Error Taxonomy                           |

---

**Current Focus:** [05-core-api-pets.md](./05-core-api-pets.md)
