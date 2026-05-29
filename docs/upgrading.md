# Upgrading Dependencies

Dependency upgrades are normal maintenance, but not every upgrade has the same risk.

- Patch and minor updates are usually routine.
- Major updates are deliberate engineering work.
- The important distinction is not only "how do we install updates?" but also "how do we notice versions that our current constraints intentionally do not allow?"

This project is a Python FastAPI service:

- Dependencies are declared in `pyproject.toml`.
- Local development uses `venv` plus `pip install -e ".[dev]"`.
- `uv` is optional for local development, not required by the repo.
- The Dockerfile installs production dependencies into an image during build.
- There is currently no committed dependency lockfile.

Because there is no lockfile, dependency upgrades here mean editing version constraints in `pyproject.toml`, reinstalling the environment, rebuilding the image, and verifying behavior.

## Upgrade Tiers

| Type  | Example          | Usual handling                        |
| ----- | ---------------- | ------------------------------------- |
| Patch | `1.2.3 -> 1.2.4` | Routine update                        |
| Minor | `1.2 -> 1.3`     | Routine update with full verification |
| Major | `1.x -> 2.0`     | Planned upgrade branch                |

Even patch and minor updates can break in practice, so every update should be followed by the relevant tests and checks.

## Execution Modes

There are two useful ways to run this protocol:

- Rehearsal mode: non-mutating checks that show what would change.
- Real update mode: actually change constraints, reinstall dependencies, and rebuild the Docker image.

Use rehearsal mode first when you want a safe signal about whether the current branch is healthy enough for upgrade work.

### Rehearsal Mode

With the virtual environment activated:

```bash
python -m pip list --outdated
python -m pip install --upgrade --dry-run -e ".[dev]"
```

Then run the same verification suite you would use after a real update.

## Routine Updates

For routine dependency maintenance, inspect what is outdated first:

```bash
source .venv/bin/activate
python -m pip list --outdated
```

If an update is inside the currently allowed constraints, reinstall the environment:

```bash
python -m pip install --upgrade -e ".[dev]"
```

Then verify:

```bash
pytest
ruff check .
mypy src
docker compose build
```

Inspect the diff afterward:

```bash
git status --short
git diff --stat
```

If no files changed, the update only affected the local environment. That can still be useful for catching breakage, but there is nothing to commit unless constraints or docs changed.

## How To Detect New Major Versions

This is the part people often miss.

Most dependencies use lower-bound constraints such as `fastapi>=0.135.3` or `pydantic>=2.9`. Unlike caret ranges in some ecosystems, these do not cap the next major version. That means a fresh install may accept a future major if it satisfies the lower bound and Python requirements.

Use:

```bash
python -m pip list --outdated
```

Then inspect direct dependencies in `pyproject.toml`. Pay particular attention to packages that form public or security-sensitive contracts:

- `fastapi`
- `pydantic`
- `pydantic-settings`
- `httpx`
- `python-jose[cryptography]`
- `cryptography`
- `redis[hiredis]`
- `structlog`
- `pytest`
- `ruff`
- `mypy`

Interpretation:

- `pip list --outdated` answers: "What newer versions exist compared with this local environment?"
- `pyproject.toml` answers: "What versions does the project allow?"
- Because the project has no lockfile, a clean install in CI or Docker can resolve newer versions than an older local virtualenv.

If we need reproducible dependency resolution, introduce a lockfile intentionally as its own change instead of mixing it into a routine upgrade.

## Security Checks

Run a vulnerability scan when changing dependency constraints or before a release.

If `pip-audit` is installed:

```bash
pip-audit
```

If it is not installed, either install it temporarily or use another Python package audit tool. Do not add new audit tooling to the repo unless we decide to make it part of the normal workflow.

## Recommended Cadence

Use two different rhythms:

### 1. Routine dependency maintenance

Do this regularly:

```bash
python -m pip list --outdated
python -m pip install --upgrade -e ".[dev]"
pytest
ruff check .
mypy src
docker compose build
```

### 2. Major-version and contract scan

Do this on a schedule, for example once a month:

```bash
python -m pip list --outdated
```

Then compare the listed packages against `pyproject.toml` and decide whether any lower-bound-only constraints should be tightened or deliberately raised.

## Major Upgrade Process

When taking a major version, treat it as a small project.

### Principles

- Upgrade one major dependency at a time when feasible.
- Read the official upgrade guide before changing code.
- Start from a clean baseline with passing tests and analysis.
- Treat auth, crypto, OpenAPI, and GPT tool-schema changes as high risk.
- Prefer small, reviewable commits over one giant "upgrade everything" diff.

### Workflow

#### 1. Read the upstream guide

Examples:

- FastAPI release notes and migration notes
- Pydantic migration guide
- httpx release notes
- cryptography changelog
- redis-py release notes
- pytest, ruff, and mypy release notes for dev-tool upgrades

#### 2. Establish a clean baseline

```bash
source .venv/bin/activate
pytest
ruff check .
mypy src
docker compose build
```

If the baseline is already broken, fix that first.

#### 3. Create a dedicated branch

```bash
git checkout -b upgrade/pydantic-3
```

#### 4. Upgrade explicitly

Edit `pyproject.toml` to set the intended target constraint, then reinstall:

```bash
python -m pip install --upgrade -e ".[dev]"
```

For production dependency changes, also rebuild the image:

```bash
docker compose build --no-cache connector
```

#### 5. Fix breakages iteratively

Suggested order:

1. Type and import errors
2. Unit tests
3. OAuth flow and JWT/crypto behavior
4. OpenAPI schema and Custom GPT action compatibility
5. Docker build and `/health`

#### 6. Verify the external contract

If the upgrade changes request/response models, auth behavior, or generated OpenAPI:

```bash
docker compose up -d --build
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8001/openapi.json | head
```

Then test at least one read action and one write action through the connector.

#### 7. Document what changed

If the upgrade taught us project-specific lessons, add them to this document so the next upgrade starts from real local knowledge, not memory.

### Project notes (2026-05)

- **mypy 2.x**: Stricter Redis return types (`bytes | str | None` even with `decode_responses=True`) and unused `type: ignore` comments. Prefer explicit `isinstance` checks or `int()` casts in `src/core/redis.py` and `src/core/admin_events.py` instead of blanket ignores.
- **mypy 2.x**: Reusing the same loop variable name (`summary`) across consecutive `zip()` loops can confuse assignment narrowing; use distinct names per loop (for example `vacc_summary` / `weight_summary`).
- **mypy 2.x**: Bare `list[dict]` annotations need parameters (`list[dict[str, Any]]`).
- **redis 8.x**: No code changes required here; async client usage stayed the same.
- **cryptography 48.x**: No code changes required; JWT/crypto tests passed unchanged.
- **FastAPI 0.136.x**: Pulls **Starlette 1.x** transitively. Watch release notes if middleware or exception handling changes.

## Deployment Note

This repo uses `dev` as the normal source branch and `main` as the production release target. See `docs/release.md` before releasing.

Woodpecker can deploy branches through SSH when configured by the operator. Treat pushes to deployment branches as potentially live deploy triggers and verify pipeline outcome plus `/health` afterward.

## What Not To Assume

- A successful local reinstall does not mean Docker will build unless production dependencies are also covered.
- With no lockfile, a clean install can resolve newer versions than an old virtualenv.
- OpenAPI shape is part of the Custom GPT contract; schema changes need GPT refresh work.
- Auth, token, crypto, and rate-limit behavior deserve extra scrutiny after dependency upgrades.

## Current Versions

Lower bounds in `pyproject.toml` (last verified 2026-05-30):

| Dependency | Constraint | Resolved (local venv) |
| ---------- | ---------- | --------------------- |
| Python     | >=3.12     | 3.12                  |
| FastAPI    | >=0.136.3  | 0.136.3               |
| Pydantic   | >=2.13     | 2.13.4                |
| pydantic-settings | >=2.14 | 2.14.1            |
| uvicorn    | >=0.48.0   | 0.48.0                |
| httpx      | >=0.28     | 0.28.1                |
| cryptography | >=48.0.0 | 48.0.0                |
| Redis client | >=8.0.0  | 8.0.0                 |
| pytest     | >=9.0.3    | 9.0.3                 |
| ruff       | >=0.15.15  | 0.15.15               |
| mypy       | >=2.1.0    | 2.1.0                 |

Starlette is not pinned directly; a clean install currently resolves **1.2.0** via FastAPI.
