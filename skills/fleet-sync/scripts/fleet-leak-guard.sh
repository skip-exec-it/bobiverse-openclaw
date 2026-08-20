#!/usr/bin/env bash
# fleet-leak-guard.sh — Pre-push/pre-commit hook to prevent committing sensitive files
# Usage: fleet-leak-guard.sh [--staged|--all] [--verbose]
#   --staged: Check only staged files (for pre-commit)
#   --all: Check all files in working directory (more thorough but slower)
#   --verbose: Print details of matches found
#
# This script implements a leak guard by checking for files matching
# sensitive patterns (similar to those excluded in fleet-github-framework.sh).
# Exit code 0: safe to proceed (no matches found)
# Exit code 1: dangerous files detected (abort commit/push)
#
# Can be used as:
#   pre-commit: .git/hooks/pre-commit -> ../../skills/fleet-sync/scripts/fleet-leak-guard.sh
#   pre-push:   .git/hooks/pre-push   -> ../../skills/fleet-sync/scripts/fleet-leak-guard.sh

set -euo pipefail

# Default to checking staged files (safe for pre-commit/pre-push)
CHECK_STAGED=true
CHECK_ALL=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --all)
      CHECK_STAGED=false
      CHECK_ALL=true
      shift
      ;;
    --staged)
      CHECK_STAGED=true
      CHECK_ALL=false
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Define dangerous patterns (matches fleet-github-framework.sh excludes)
declare -a DANGEROUS_PATTERNS=(
  "vault.dat"
  "*vault-key*"
  "*.key"
  "*.pem"
  ".env"
  "*secret*"
  "*token*"
  ".git/"
  "__pycache__/"
  "*.pyc"
  "node_modules/"
  "*.venv/"
  "venv/"
  "state/"
  "*.log"
)

# Function to check if a path matches any dangerous pattern
is_dangerous() {
  local path="$1"
  local rel_path
  
  # Make path relative to git root if possible
  if git rev-parse --show-toplevel > /dev/null 2>&1; then
    local git_root
    git_root=$(git rev-parse --show-toplevel)
    # Try to make relative, but fall back to full path if outside repo
    if [[ "$path" == "$git_root"* ]]; then
      rel_path="${path#"$git_root"/}"
    else
      rel_path="$path"
    fi
  else
    rel_path="$path"
  fi
  
  # Check against each pattern
  for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    # Convert glob pattern to regex for matching
    # Simple approach: convert * to .* and escape dots, then use bash pattern matching
    local regex_pattern
    regex_pattern=$(echo "$pattern" | sed 's/\./\\./g; s/\*/.*/g')
    if [[ "$rel_path" =~ $regex_pattern ]]; then
      return 0  # Match found
    fi
  done
  return 1  # No match
}

# Function to check files - returns 0 if no matches, 1 if any match found
check_files() {
  local file_list="$1"
  
  # Handle empty input
  if [[ -z "$file_list" ]]; then
    return 0
  fi
  
  # Read each line and check if it matches any dangerous pattern
  while IFS=read -r file || [[ -n "$file" ]]; do
    if [[ -n "$file" ]]; then
      if is_dangerous "$file"; then
        if [[ "$VERBOSE" == "true" ]]; then
          echo "DANGER: $file matches unsafe pattern" >&2
        fi
        return 1  # Found a match - dangerous file detected
      fi
    fi
  done <<< "$file_list"
  
  # No matches found
  return 0
}

# Get list of files to check
if [[ "$CHECK_ALL" == "true" ]]; then
  # Check all files in working directory
  if [[ "$VERBOSE" == "true" ]]; then
    echo "Checking all files in working directory..." >&2
  fi
  # Use git ls-files to get tracked files
  FILE_LIST=$(git ls-files) || true
  if [[ "$VERBOSE" == "true" ]]; then
    echo "FILES TO CHECK: [$FILE_LIST]" >&2
  fi
elif [[ "$CHECK_STAGED" == "true" ]]; then
  # Check staged files (for commit)
  if [[ "$VERBOSE" == "true" ]]; then
    echo "Checking staged files..." >&2
  fi
  FILE_LIST=$(git diff --cached --name-only) || true
  if [[ "$VERBOSE" == "true" ]]; then
    echo "FILES TO CHECK: [$FILE_LIST]" >&2
  fi
else
  # Default to staged
  FILE_LIST=$(git diff --cached --name-only) || true
  if [[ "$VERBOSE" == "true" ]]; then
    echo "FILES TO CHECK: [$FILE_LIST]" >&2
  fi
fi

# Check the files
if check_files "$FILE_LIST"; then
  if [[ "$VERBOSE" == "true" ]]; then
    echo "OK: No dangerous files detected" >&2
  fi
  exit 0
else
  if [[ "$VERBOSE" == "true" ]]; then
    echo "ABORT: Dangerous files found - remove them or add to .gitignore" >&2
  fi
  exit 1
fi