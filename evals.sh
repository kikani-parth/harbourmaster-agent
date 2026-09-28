#!/bin/sh
# Runs the eval suite. Prints a human-readable summary. Exits non-zero if it fails.
# Exercises the agent only by invoking ./run.sh -- see SPEC.md 12.
set -eu
cd "$(dirname "$0")"

# See run.sh: keep Python in UTF-8 mode so "§" survives on Windows.
export PYTHONUTF8=1

if [ -n "${HARBOURMASTER_PYTHON:-}" ]; then
    PY="$HARBOURMASTER_PYTHON"
elif [ -x .venv/bin/python3 ]; then
    PY=.venv/bin/python3
elif [ -x .venv/Scripts/python.exe ]; then
    PY=.venv/Scripts/python.exe
else
    PY=python3
fi

exec "$PY" evals/runner.py
