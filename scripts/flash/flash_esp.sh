#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# OpenEVSE ESP32 Flash Helper (Linux / macOS compatible)
#
# This script mirrors the Windows batch helper:
#   1. Locates Python 3
#   2. Creates/uses a local virtual environment (.venv)
#   3. Installs/updates esptool + pyserial
#   4. Invokes scripts/flash_esp32.py passing all user arguments
#
# Usage:
#   ./scripts/setup_and_flash.sh                 # interactive prompts
#   ./scripts/setup_and_flash.sh -f firmware.bin -p /dev/ttyUSB0 --erase
#   ./scripts/setup_and_flash.sh --file build/firmware.elf --port /dev/ttyUSB0
#
# Non‑interactive example:
#   ./scripts/setup_and_flash.sh --file firmware.bin --port /dev/ttyUSB0 --non-interactive
#
# NOTE: No "pause" equivalent is added (not customary on Unix shells).
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR%/scripts}"  # assume script lives in repo_root/scripts
cd "$REPO_ROOT"

log() { printf "[+] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*" >&2; }
err() { printf "[ERROR] %s\n" "$*" >&2; exit 1; }

# --- Locate Python 3 ---------------------------------------------------------
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD=python
else
  err "Python 3 not found. Install Python 3 and re-run."
fi

# --- Create virtual environment ----------------------------------------------
if [ ! -d .venv ]; then
  log "Creating virtual environment (.venv) ..."
  "$PYTHON_CMD" -m venv .venv || err "Failed to create virtual environment"
fi

# shellcheck disable=SC1091
source .venv/bin/activate || err "Failed to activate virtual environment"

# --- Upgrade pip quietly -----------------------------------------------------
log "Upgrading pip (quiet) ..."
python -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || warn "pip upgrade encountered a warning"

# --- Install dependencies ----------------------------------------------------
log "Installing/Updating esptool + pyserial ..."
python -m pip install --upgrade esptool pyserial >/dev/null || err "Dependency installation failed"

# --- Show summary ------------------------------------------------------------
log "Environment ready. Launching flash utility ..."

# --- Execute Python flashing script -----------------------------------------
PY_FLASH_SCRIPT="scripts/flash_esp32.py"
if [ ! -f "$PY_FLASH_SCRIPT" ]; then
  err "Flashing script '$PY_FLASH_SCRIPT' not found."
fi

# Preserve all user arguments
python "$PY_FLASH_SCRIPT" "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  log "Flash script finished successfully."
else
  err "Flash script exited with code $EXIT_CODE"
fi

exit $EXIT_CODE
