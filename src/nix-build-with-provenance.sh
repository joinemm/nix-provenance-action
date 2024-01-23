#!/usr/bin/env bash

set -x
set -e

PROVENANCE_TIMESTAMP_BEGIN="$(date +%s)"
echo "--- Starting nix build ---"

nix build "${@}"
PROVENANCE_EXTERNAL_PARAMETERS="$(jq -n --arg target "$1" --arg build-args "${2:@}" '$ARGS.named')"

PROVENANCE_TIMESTAMP_END="$(date +%s)"
echo "--- Build done ---"
echo "Generating provenance..."

export PROVENANCE_TIMESTAMP_BEGIN
export PROVENANCE_TIMESTAMP_END
export PROVENANCE_EXTERNAL_PARAMETERS
export PROVENANCE_OUTPUT_FILE=provenance.json

python main.py "$1"
