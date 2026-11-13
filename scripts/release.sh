#!/usr/bin/env bash
# Publish a GitHub release for the version in manifest.json, with that
# version's section of CHANGELOG.md as the notes. Does nothing if the release
# already exists, so it is safe to run on every push to main.
#
# Usage: scripts/release.sh           publish (needs gh and GH_TOKEN; used by CI)
#        scripts/release.sh --check   only check the changelog has the section
set -euo pipefail
cd "$(dirname "$0")/.."

version=$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' custom_components/ticktick/manifest.json)
notes=$(awk -v heading="## $version" '
    $0 == heading { found = 1; next }
    found && /^## [0-9]/ { exit }
    found' CHANGELOG.md)

if [ -z "$(printf '%s' "$notes" | tr -d '[:space:]')" ]; then
    echo "::error::CHANGELOG.md has no '## $version' section for the manifest version"
    exit 1
fi
if [ "${1:-}" = "--check" ]; then
    echo "CHANGELOG.md has a section for $version"
    exit 0
fi

if gh release view "$version" >/dev/null 2>&1; then
    echo "Release $version already exists"
    exit 0
fi
gh release create "$version" --target "${GITHUB_SHA:-main}" --title "$version" --notes "$notes"
