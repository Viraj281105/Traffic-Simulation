#!/usr/bin/env bash
# Shell wrapper script to execute JSON Schema validation in local and CI environments.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/validate_schemas.py"

# Run Python validation script
if command -v python3 &>/dev/null; then
    python3 "${PYTHON_SCRIPT}"
elif command -v python &>/dev/null; then
    python "${PYTHON_SCRIPT}"
else
    echo "Error: Python is required to run schema validations." >&2
    exit 1
fi
