#!/bin/sh
# Seed the catalog from the CSVs before serving (ADR-0002): the server only
# starts once the database is ready, and a failed seed stops the container.
set -eu

python -m emporio.seed
exec "$@"
