#!/usr/bin/env bash
# Build the current Darbot Python SDK checkout; do not fetch upstream branches.
# Usage: scripts/build-docs.sh [output-dir]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

bash scripts/docs/build.sh

OUTPUT_DIR="${1:-site}"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
if [[ "$OUTPUT_DIR" != "$REPO_ROOT/site" ]]; then
    cp -a "$REPO_ROOT/site/." "$OUTPUT_DIR/"
fi
