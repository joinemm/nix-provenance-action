#!/usr/bin/env bash

set -e

PROVENANCE_TIMESTAMP_BEGIN="$(date +%s)"

echo "--- Starting nix build ---"

nix build "${@}"

PROVENANCE_EXTERNAL_PARAMETERS="$(jq -n --arg target "$1" --arg build-args "${2:@}" '$ARGS.named')"
PROVENANCE_TIMESTAMP_FINISHED="$(date +%s)"

echo "--- Build done ---"
echo "Generating provenance..."

export PROVENANCE_TIMESTAMP_BEGIN
export PROVENANCE_TIMESTAMP_FINISHED
export PROVENANCE_EXTERNAL_PARAMETERS

nix run github:tiiuae/sbomnix#provenance "$1"
