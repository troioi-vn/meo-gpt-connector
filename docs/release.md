# Release Runbook

Use this document when cutting a new connector release (`vX.Y.Z`).

## Core rules

- Release source branch is `dev`.
- Release target branch is `main`.
- Always create an annotated tag on `main`.
- Never run `git push --tags`.
- Git tags and GitHub Releases are separate things.
- Version must be bumped before merge. Do not skip this.

## Version checklist

When bumping from `vA.B.C` to `vX.Y.Z`, update:

- `pyproject.toml`
- `src/main.py`
- any version examples in docs that would become misleading

Quick check:

```bash
rg -n 'version = "|version="' pyproject.toml src docs
```

## Preflight

Run from repo root:

```bash
git fetch --all --tags --prune
git status --short --branch
git tag -l 'v*' --sort=version:refname | tail -n 10
git branch --show-current
```

Checklist:

- Worktree is clean.
- You are on `dev`.
- `dev` contains all intended release changes.
- Tests already passed for the release candidate.
- You know the previous release tag.

## Release procedure

### 1. Choose next version

```bash
NEW=v0.2.4
OLD=v0.2.3
```

### 2. Review release delta

```bash
git log --oneline ${OLD}..HEAD
git diff --stat ${OLD}..HEAD
```

Write a short release summary before tagging:

- one title line
- one short summary sentence or paragraph
- flat bullets for meaningful user-facing changes

### 3. Bump version on `dev`

Update:

- `pyproject.toml`
- `src/main.py`

Then verify:

```bash
rg -n "${NEW#v}" pyproject.toml src/main.py docs
```

Commit:

```bash
git add pyproject.toml src/main.py docs
git commit -m "chore(release): bump version to ${NEW}"
```

### 4. Merge `dev` into `main`

```bash
git checkout main
git pull --ff-only origin main
git merge --ff-only dev
```

If fast-forward is not possible, stop and resolve branch state on `dev` first.

### 5. Create annotated tag

```bash
git tag -a ${NEW} -m "${NEW} - <short title>" -m "<release notes body>"
```

### 6. Push `main` and tag

```bash
git push origin main
git push origin ${NEW}
```

### 7. Create GitHub Release

```bash
gh release create ${NEW} \
  --verify-tag \
  --notes-from-tag \
  --title "${NEW} - <short title>" \
  --latest
```

### 8. Sync `dev` with `main`

```bash
git checkout dev
git merge main --ff-only
git push origin dev
```

## Post-release verification

### Branch and tag

```bash
git show -s --oneline ${NEW}
gh release view ${NEW}
git log --oneline --decorate -n 5 --graph
```

### Running connector

```bash
curl -f https://gpt-connector.meo-mai-moi.com/health
```

Expect the deployed version to match `${NEW#v}`.

### OpenAPI and GPT refresh

If the release changes tool schema, descriptions, or auth behavior:

```bash
curl -fsSL https://gpt-connector.meo-mai-moi.com/openapi.json | head
```

Checklist:

- live OpenAPI contains the new fields/enums/descriptions
- Custom GPT action schema is re-imported from the live OpenAPI URL
- OAuth still works
- one read action works
- one write action works

## Failure handling

- If version was not bumped before merge, fix it immediately on `dev`, merge again, and retag with a new version.
- If `main` push succeeds but tag push fails, retry only the tag push.
- If the wrong tag message was published, create a new version tag instead of force-moving the old one.
- If OpenAPI changed but the GPT was not reloaded, the deployment is incomplete.

## Release note template

```text
vX.Y.Z - <short title>

<One short summary paragraph.>

- <User-facing change 1>
- <User-facing change 2>
- <User-facing change 3>
```
