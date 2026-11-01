#!/bin/sh
# Seed the catalog from the CSVs before serving (ADR-0002): the server only
# starts once the database is ready, and a failed seed stops the container.
set -eu

# The audit log folder is a bind mount (./logs on the host). On Linux a folder
# Docker created for the mount belongs to root; say so instead of failing quietly
# later (chat keeps working, the log would only warn on stderr).
log_dir=$(dirname "${LOG_PATH:-/app/logs/audit.jsonl}")
if ! mkdir -p "$log_dir" 2>/dev/null || [ ! -w "$log_dir" ]; then
    echo "warning: $log_dir is not writable by uid $(id -u); audit log disabled." >&2
    echo "         on the host run: mkdir -p logs && sudo chown 10001 logs" >&2
fi

python -m emporio.seed
exec "$@"
