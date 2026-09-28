#!/bin/sh
# Reads one JSON object per line on stdin, writes one per line on stdout.
# Diagnostics go to stderr. See SPEC.md 1.
#
# The agent is Python, in harbourmaster/. This script is glue only.
# Prefers the project venv (boto3 lives there); falls back to whatever python3
# is on the path, so the shipped script does not depend on a directory that is
# not in the submission.
set -eu
cd "$(dirname "$0")"

# Windows Python defaults stdio and files to cp1252, which writes "§" as 0xA7 and
# breaks every consumer expecting UTF-8 JSONL. Harmless on Linux.
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

exec "$PY" -m harbourmaster.cli
