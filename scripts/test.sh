#!/usr/bin/env bash
# Run lint and tests in Docker, the same way CI does.
# Usage: scripts/test.sh [pytest args]
set -euo pipefail
cd "$(dirname "$0")/.."

# Git Bash on Windows needs a Windows-style path for the volume mount
repo="$(pwd -W 2>/dev/null || pwd)"

docker build -q -f tests/Dockerfile -t ticktick-hass-test . >/dev/null
MSYS_NO_PATHCONV=1 docker run --rm -v "$repo:/app" ticktick-hass-test \
    sh -c 'ruff check custom_components tests && pytest "$@"' sh "$@"
