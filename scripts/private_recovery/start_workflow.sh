#!/bin/sh
set -eu
umask 077
ulimit -c 0
exec /opt/cashout-workflow/bin/python /app/scripts/private_recovery/workflow.py
