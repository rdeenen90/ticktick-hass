#!/usr/bin/env bash
# Start a throwaway Home Assistant on http://localhost:8123 with this
# integration loaded. Its configuration lives in ./config (not committed).
# Run inside the devcontainer, or anywhere requirements_test.txt is installed.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p config
if [ ! -f config/configuration.yaml ]; then
    cat > config/configuration.yaml <<'YAML'
# Just enough of Home Assistant to set up and use the integration
frontend:
config:
my:

logger:
  default: info
  logs:
    custom_components.ticktick: debug
YAML
fi

# Home Assistant installs its runtime packages into the user site-packages;
# Python only puts that folder on its path if it exists at startup.
mkdir -p "$(python -m site --user-site)"

# Lets Home Assistant find ./custom_components without copying it into ./config
export PYTHONPATH="${PYTHONPATH:-}:${PWD}"

exec hass --config "${PWD}/config" --debug
