# Release Guide

Simple, repeatable steps to cut a new release.

## Version source of truth

- **`pyproject.toml`**: `[project] version = "..."` is the canonical version.
- **Git tags**: Annotated tags (`v0.1.0`) mark each release. No separate CHANGELOG file — git
  tags and commit messages are the source of truth.
- **Runtime**: The `/health` endpoint returns the running version. The connector reads it from
  the installed package metadata at startup (`importlib.metadata.version("meo-gpt-connector")`).

## Branching strategy

```
main    — production only, always stable
dev     — integration branch, features merge here first
feature/... — short-lived feature branches off dev
```

Preferred: never commit directly to `main`; all work goes through `dev` first.
If the repo is temporarily running without a `dev` branch, cut the release from `main`
and re-introduce `dev` afterward.

## How to release a new version

### 1. Ensure `dev` is ready

All features for the release are merged into `dev`. Tests pass. Docker build succeeds.

Before cutting a release that depends on upstream auth or route behavior, verify the connector against the current Meo Mai Moi backend contract. In particular, confirm that exchanged Sanctum tokens still carry the generic PAT abilities needed for protected programmatic routes such as `GET /api/my-pets` and `POST /api/pets`.

### 2. Bump the version on `dev`

Edit `pyproject.toml`:

```toml
[project]
version = "0.2.3"
```

Commit on `dev`:

```bash
git add pyproject.toml
git commit -m "chore(release): bump version to v0.2.3"
```

### 3. Merge `dev` into `main`

Use `--no-ff` to create a merge commit so the release boundary is visible in history:

```bash
git checkout main
git merge --no-ff dev -m "Merge dev into main for v0.2.3 release"
```

### 4. Tag the release

Create an annotated tag on `main`:

```bash
git tag -a v0.2.3 -m "v0.2.3 - Add birthday context to pets overview"
```

### 5. Push

Push the branch and the tag separately:

```bash
git push origin main
git push origin v0.2.3
```

### 6. Create GitHub release

Publish a GitHub release for the tag:

```bash
gh release create v0.2.3 \
  --title "v0.2.3" \
  --generate-notes
```

### 7. Sync `dev` with `main`

Keep dev aligned so it includes the merge commit:

```bash
git checkout dev
git merge main --ff-only
git push origin dev
```

### 8. Verify

```bash
# Check version is correct on the running connector
curl -f https://gpt.troioi.vn/health
# Expect: {"status": "ok", "version": "0.2.3", "main_app_reachable": true}
```

For releases that touch upstream auth/error handling, also do one small live proof against the current backend:

- complete the OAuth exchange
- call a PAT-gated read through the connector (`GET /pets` -> upstream `GET /api/my-pets`)
- call a PAT-gated write through the connector (`POST /pets` -> upstream `POST /api/pets`)
- confirm upstream `429` responses still surface as connector `429` with any quota metadata preserved

## Viewing changes between releases

```bash
# Summary of commits between two releases
git log --oneline v0.2.2..v0.2.3

# Full diff between releases
git diff v0.2.2..v0.2.3

# All releases
git tag -l 'v*'
```

## v0.2.3 release notes

- Preserved upstream `429` responses as connector `429` instead of collapsing them into generic `502` errors.
- Preserved safe upstream quota metadata in connector error payloads for daily quota and rate-limit debugging.
- Added regression coverage proving that exchanged Sanctum tokens can still use PAT-gated upstream routes such as `GET /api/my-pets` and `POST /api/pets`.
- Added GPT onboarding guidance for the new-account flow: ask which email the user wants to use before sending them into Connect Account, and warn when email verification may delay protected pet tools.
