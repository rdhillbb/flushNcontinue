#!/bin/sh
# Local KB metadata only; no application tests, network or global settings.
set -eu
KB_PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec python3 "$KB_PROJECT_ROOT/scripts/kb/kb_tools.py" --repo "$KB_PROJECT_ROOT" health
