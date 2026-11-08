#!/usr/bin/env bash
# Launches MetalEQ. Run ./install.sh first if dependencies are missing.
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Run ./install.sh first." >&2
    exit 1
fi

if ! python3 -c 'import PyQt6.QtWidgets, gi' >/dev/null 2>&1; then
    echo "MetalEQ's dependencies (PyQt6 / PyGObject) are missing. Run ./install.sh first." >&2
    exit 1
fi

exec python3 main.py "$@"
