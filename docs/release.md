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

### 2. Bump the version on `dev`

Edit `pyproject.toml`:

```toml
[project]
version = "0.2.1"
```

Commit on `dev`:

```bash
git add pyproject.toml
git commit -m "chore(release): bump version to v0.2.1"
```

### 3. Merge `dev` into `main`

Use `--no-ff` to create a merge commit so the release boundary is visible in history:

```bash
git checkout main
git merge --no-ff dev -m "Merge dev into main for v0.2.1 release"
```

### 4. Tag the release

Create an annotated tag on `main`:

```bash
git tag -a v0.2.1 -m "v0.2.1 - Add pets_overview bulk tool and GPT routing guidance"
```

### 5. Push

Push the branch and the tag separately:

```bash
git push origin main
git push origin v0.2.1
```

### 6. Create GitHub release

Publish a GitHub release for the tag:

```bash
gh release create v0.2.1 \
  --title "v0.2.1" \
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
# Expect: {"status": "ok", "version": "0.2.1", "main_app_reachable": true}
```

## Viewing changes between releases

```bash
# Summary of commits between two releases
git log --oneline v0.2.0..v0.2.1

# Full diff between releases
git diff v0.2.0..v0.2.1

# All releases
git tag -l 'v*'
```

## v0.2.1 release notes

- Added `POST /pets/overview` as a bulk GPT tool for cross-pet filtering/sorting.
- Added computed fields in overview response:
  `next_vaccination_due_at`, `next_vaccination_name`, and `vaccination_data_status`.
- Added GPT routing guidance to prefer `pets_overview` for ranking/comparison requests
  instead of per-pet vaccination loops.
