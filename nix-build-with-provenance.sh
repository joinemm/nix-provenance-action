#!/usr/bin/env bash

set -e

PROVENANCE_TIMESTAMP_BEGIN="$(date +%s)"
echo "--- Starting nix build ---"

nix build "${@}"
PROVENANCE_BUILD_COMMAND="nix build ${*}"

PROVENANCE_TIMESTAMP_END="$(date +%s)"
echo "--- Build done ---"
echo "Generating provenance..."

export PROVENANCE_TIMESTAMP_BEGIN
export PROVENANCE_TIMESTAMP_END
export PROVENANCE_BUILD_COMMAND
export PROVENANCE_OUTPUT_FILE=provenance.json

python main.py "$1"
