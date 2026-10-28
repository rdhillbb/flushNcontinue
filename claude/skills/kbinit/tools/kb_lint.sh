#!/bin/sh
# kb_lint.sh — thin wrapper: the ONE KB lint is `kb_tools.py lint`; this prints its text report.
# Sizes, next free IDs, freshness, dead pointers, secret hygiene, import check, skill parity,
# resume read cost. Read-only. Exit 1 only on hard errors; warnings exit 0. Extra args pass through.
set -eu
KB_PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec python3 "$KB_PROJECT_ROOT/scripts/kb/kb_tools.py" --repo "$KB_PROJECT_ROOT" lint --text "$@"
