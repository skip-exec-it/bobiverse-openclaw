#!/bin/bash
# fleet-sync.sh — Mirror shared skills into local workspace
# Run every 30 minutes via cron (offset from heartbeat cadence)
#
# Cron example (edit with: crontab -e):
#   */30 * * * * CLAWDBOT_HOME=/mnt/fleet-home /usr/local/bin/fleet-sync.sh

set -euo pipefail

: "${CLAWDBOT_HOME:?CLAWDBOT_HOME must be set}"

WORKSPACE="${HOME}/.openclaw/workspace"
SKILLS_SRC="${CLAWDBOT_HOME}/skills"
SKILLS_DST="${WORKSPACE}/skills"
SHARED_SRC="${CLAWDBOT_HOME}/shared"
LOG="${WORKSPACE}/fleet-sync.log"

mkdir -p "${SKILLS_DST}"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "$(timestamp) fleet-sync: starting" >> "${LOG}"

# Mirror skills (shared → local)
if [ -d "${SKILLS_SRC}" ]; then
    rsync -a --delete \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='node_modules' \
        "${SKILLS_SRC}/" "${SKILLS_DST}/"
    echo "$(timestamp) fleet-sync: skills synced" >> "${LOG}"
else
    echo "$(timestamp) fleet-sync: WARN skills source not found: ${SKILLS_SRC}" >> "${LOG}"
fi

# Mirror shared docs (shared → local workspace)
if [ -d "${SHARED_SRC}" ]; then
    rsync -a \
        --exclude='waiver-register.csv' \
        "${SHARED_SRC}/" "${WORKSPACE}/"
    echo "$(timestamp) fleet-sync: shared docs synced" >> "${LOG}"
fi

echo "$(timestamp) fleet-sync: done" >> "${LOG}"
