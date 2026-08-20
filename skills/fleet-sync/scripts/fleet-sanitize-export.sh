#!/usr/bin/env bash
# fleet-sanitize-export.sh — Create a sanitized copy of a directory by excluding sensitive patterns
# Usage: fleet-sanitize-export.sh SOURCE_DIR DEST_DIR [--dry-run]
#   SOURCE_DIR: Directory to sanitize and copy from
#   DEST_DIR: Directory to copy sanitized content to
#   --dry-run: Show what would be copied without actually copying
#
# This script generalizes the exclude pattern approach used in fleet-github-framework.sh
# and fleet-github-backup.sh to create a safe copy for sharing/publishing.
#
# Excludes common sensitive file patterns by default, but can be customized via
# FLEET_SANITIZE_EXCLUDES environment variable (comma-separated list of patterns).

set -euo pipefail

# Default exclusion patterns (same as fleet-github-framework.sh)
DEFAULT_EXCLUDES=(
  'vault.dat' '*vault-key*' '*.key' '*.pem'
  '.env' '*secret*' '*token*'
  '.git/' '__pycache__/' '*.pyc'
  'node_modules/' '*.venv/' 'venv/'
  'state/' '*.log'
  '.DS_Store' 'Thumbs.db'
)

# Parse arguments
DRY_RUN=false
if [[ "${#}" -lt 2 ]]; then
  echo "Usage: $0 SOURCE_DIR DEST_DIR [--dry-run]" >&2
  exit 1
fi

SOURCE_DIR="${1}"
DEST_DIR="${2}"
shift 2

# Handle remaining arguments
while [[ "${#}" -gt 0 ]]; do
  case "${1}" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown option: ${1}" >&2
      exit 1
      ;;
  esac
done

# Validate source directory
if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "Error: Source directory not found: ${SOURCE_DIR}" >&2
  exit 1
fi

# Build exclude patterns array
EXCLUDES=()
if [[ -n "${FLEET_SANITIZE_EXCLUDES:-}" ]]; then
  # Use custom exclusions from environment (comma-separated list of patterns)
  IFS=',' read -ra PATTERNS <<< "$FLEET_SANITIZE_EXCLUDES"
  for pattern in "${PATTERNS[@]}"; do
    # Trim whitespace
    pattern="$(echo -e "${pattern}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [[ -n "${pattern}" ]]; then
      EXCLUDES+=(--exclude "${pattern}")
    fi
  done
else
  # Use default exclusions
  for pattern in "${DEFAULT_EXCLUDES[@]}"; do
    EXCLUDES+=(--exclude "${pattern}")
  done
fi

# Create destination directory
mkdir -p "${DEST_DIR}"

# Function to log with timestamp
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(timestamp) fleet-sanitize-export: $*"; }

log "Starting sanitized export from '${SOURCE_DIR}' to '${DEST_DIR}'"
if [[ "${DRY_RUN}" == true ]]; then
  log "DRY RUN: No files will be copied"
fi

# Build rsync command
RSYNC_CMD=(rsync -a --delete "${EXCLUDES[@]}")

if [[ "${DRY_RUN}" == true ]]; then
  RSYNC_CMD+=(--dry-run)
fi

RSYNC_CMD+=("${SOURCE_DIR}/" "${DEST_DIR}/")

# Execute rsync
if "${RSYNC_CMD[@]}"; then
  log "Sanitized export completed successfully"
else
  log "Error during sanitized export"
  exit 1
fi