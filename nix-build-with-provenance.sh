#!/usr/bin/env bash

set -e

PROVENANCE_TIMESTAMP_BEGIN="$(date +%s)"
echo "--- Starting nix build ---"

nix build "$1" "${@:2}"
PROVENANCE_BUILD_COMMAND="nix build $1 ${*:2}"

PROVENANCE_TIMESTAMP_END="$(date +%s)"
echo "--- Build done ---"
echo "Generating provenance..."

export PROVENANCE_TIMESTAMP_BEGIN
export PROVENANCE_TIMESTAMP_END
export PROVENANCE_BUILD_COMMAND

python main.py "$1"
