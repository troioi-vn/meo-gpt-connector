#!/usr/bin/env bash

set -euo pipefail

deploy_path="${1:?deploy path is required}"
deploy_branch="${2:?deploy branch is required}"

case "$deploy_branch" in
  main)
    expected_port="8001"
    ;;
  dev)
    expected_port="8002"
    ;;
  *)
    echo "Unsupported deploy branch: $deploy_branch" >&2
    exit 1
    ;;
esac

cd "$deploy_path"

if [ ! -f .env ]; then
  echo "Missing $deploy_path/.env" >&2
  exit 1
fi

health_url="http://127.0.0.1:${expected_port}/health"

docker compose up -d --build

timeout 180 bash -lc "until curl -fsS '$health_url' >/dev/null; do sleep 5; done"

docker compose ps

if ! docker compose port connector 8000 | grep -q ":$expected_port$"; then
  echo "Expected published port $expected_port was not found after deploy." >&2
  exit 1
fi
