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

Never commit directly to `main`. All work goes through `dev` first.

## How to release a new version

### 1. Ensure `dev` is ready

All features for the release are merged into `dev`. Tests pass. Docker build succeeds.

### 2. Bump the version on `dev`

Edit `pyproject.toml`:

```toml
[project]
version = "0.2.0"
```

Commit on `dev`:

```bash
git add pyproject.toml
git commit -m "chore(release): bump version to v0.2.0"
```

### 3. Merge `dev` into `main`

Use `--no-ff` to create a merge commit so the release boundary is visible in history:

```bash
git checkout main
git merge --no-ff dev -m "Merge dev into main for v0.2.0 release"
```

### 4. Tag the release

Create an annotated tag on `main`:

```bash
git tag -a v0.2.0 -m "v0.2.0 - Brief description of what's in this release"
```

### 5. Push

Push the branch and the tag separately:

```bash
git push origin main
git push origin v0.2.0
```

### 6. Sync `dev` with `main`

Keep dev aligned so it includes the merge commit:

```bash
git checkout dev
git merge main --ff-only
git push origin dev
```

### 7. Verify

```bash
# Check version is correct on the running connector
curl -f https://gpt.troioi.vn/health
# Expect: {"status": "ok", "version": "0.2.0", "main_app_reachable": true}
```

## Viewing changes between releases

```bash
# Summary of commits between two releases
git log --oneline v0.1.0..v0.2.0

# Full diff between releases
git diff v0.1.0..v0.2.0

# All releases
git tag -l 'v*'
```
