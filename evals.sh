#!/bin/sh
# Runs the eval suite. Prints a human-readable summary. Exits non-zero if it fails.
# Exercises the agent only by invoking ./run.sh -- see SPEC.md 12.
set -eu
cd "$(dirname "$0")"

if [ -n "${HARBOURMASTER_PYTHON:-}" ]; then
    PY="$HARBOURMASTER_PYTHON"
elif [ -x .venv/bin/python3 ]; then
    PY=.venv/bin/python3
else
    PY=python3
fi

exec "$PY" evals/runner.py
