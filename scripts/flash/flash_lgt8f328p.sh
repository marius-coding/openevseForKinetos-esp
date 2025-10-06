#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# LGT8F328P Flash Helper (Linux/macOS)
#
# Requirements:
#   * avrdude installed and supports lgt8f328p part (recent versions or the
#     lgt8fx variant builds). On Debian/Ubuntu: sudo apt install avrdude
#   * A USB-Serial adapter or onboard programmer exposed as /dev/ttyUSB*
#
# This script:
#   1. Locates/validates avrdude
#   2. Optionally attempts install hints if not present
#   3. Prompts (or accepts args) for serial port & HEX file
#   4. Executes avrdude with recommended flags
#
# Usage examples:
#   ./scripts/flash_lgt8f328p.sh                      # interactive
#   ./scripts/flash_lgt8f328p.sh -p /dev/ttyUSB0 -f build/open_evse.ino.hex
#   ./scripts/flash_lgt8f328p.sh -p /dev/ttyUSB0 -f firmware.hex -b 115200
#
# -----------------------------------------------------------------------------
set -euo pipefail

HEX_FILE=""
PORT=""
BAUD=115200
PROGRAMMER="avrisp"
PART="lgt8f328p"
EXTRA_ARGS=""
NON_INTERACTIVE=0

usage() {
  cat <<EOF
LGT8F328P Flash Helper

Options:
  -f <file>     HEX file to flash (e.g. open_evse.ino.hex)
  -p <port>     Serial/Programmer port (e.g. /dev/ttyUSB0)
  -b <baud>     Baud rate (default: 115200)
  -P <prog>     Programmer (default: avrisp)
  -a <args>     Extra avrdude arguments (quoted)
  -y            Non-interactive (fail if required values missing)
  -h            Show this help

Examples:
  $0 -f build/open_evse.ino.hex -p /dev/ttyUSB0
  $0 -f firmware.hex -p /dev/ttyUSB0 -b 57600
EOF
}

log() { printf "[+] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*" >&2; }
err() { printf "[ERROR] %s\n" "$*" >&2; exit 1; }

while getopts ":f:p:b:P:a:yh" opt; do
  case $opt in
    f) HEX_FILE="$OPTARG" ;;
    p) PORT="$OPTARG" ;;
    b) BAUD="$OPTARG" ;;
    P) PROGRAMMER="$OPTARG" ;;
    a) EXTRA_ARGS="$OPTARG" ;;
    y) NON_INTERACTIVE=1 ;;
    h) usage; exit 0 ;;
    :) err "Option -$OPTARG requires an argument" ;;
    \?) err "Unknown option: -$OPTARG" ;;
  esac
done
shift $((OPTIND-1))

if ! command -v avrdude >/dev/null 2>&1; then
  warn "avrdude not found in PATH. Attempting installation hints..."
  if [[ "$OSTYPE" == linux* ]]; then
    echo "Try: sudo apt install avrdude   (Debian/Ubuntu)"
    echo "  or: sudo dnf install avrdude  (Fedora)"
    echo "  or: sudo pacman -S avrdude    (Arch)"
  elif [[ "$OSTYPE" == darwin* ]]; then
    echo "Try: brew install avrdude"
  fi
  if [[ $NON_INTERACTIVE -eq 1 ]]; then
    err "avrdude missing and non-interactive mode set"
  fi
  read -rp "Continue after installing avrdude? (y/N): " c
  [[ ${c,,} == y || ${c,,} == yes ]] || err "Aborting (avrdude missing)"
  command -v avrdude >/dev/null 2>&1 || err "avrdude still not found"
fi

# Prompt for missing HEX file
if [[ -z "$HEX_FILE" ]]; then
  if [[ $NON_INTERACTIVE -eq 1 ]]; then err "Missing -f HEX file"; fi
  # Auto-detect .hex files in current directory
  mapfile -t DETECTED_HEX < <(ls -1 *.hex 2>/dev/null || true)
  if (( ${#DETECTED_HEX[@]} == 1 )); then
    read -rp "Found HEX file '${DETECTED_HEX[0]}'. Use this? [Y/n]: " ans
    ans=${ans:-y}
    if [[ ${ans,,} == y || ${ans,,} == yes ]]; then
      HEX_FILE=${DETECTED_HEX[0]}
    fi
  elif (( ${#DETECTED_HEX[@]} > 1 )); then
    echo "Multiple HEX files detected:"; i=1; for h in "${DETECTED_HEX[@]}"; do echo "  $i) $h"; ((i++)); done
    read -rp "Select file [1-${#DETECTED_HEX[@]}] or press Enter to type a path: " pick
    if [[ -n "$pick" && $pick =~ ^[0-9]+$ && $pick -ge 1 && $pick -le ${#DETECTED_HEX[@]} ]]; then
      HEX_FILE=${DETECTED_HEX[$((pick-1))]}
    fi
  fi
  if [[ -z "$HEX_FILE" ]]; then
    read -rp "Enter path to HEX file: " HEX_FILE
  fi
fi

# Resolve HEX path
if [[ ! -f "$HEX_FILE" ]]; then
  err "HEX file not found: $HEX_FILE"
fi
HEX_FILE_ABS="$(readlink -f "$HEX_FILE")"

# Attempt auto port detection if not provided
if [[ -z "$PORT" ]]; then
  if [[ $NON_INTERACTIVE -eq 1 ]]; then err "Missing -p port"; fi
  SELECTABLE=()
  # Gather candidates (glob patterns that may or may not expand)
  for pattern in /dev/ttyUSB* /dev/ttyACM* /dev/cu.usbserial*; do
    for dev in $pattern; do
      [[ -e "$dev" ]] && SELECTABLE+=("$dev")
    done
  done
  if (( ${#SELECTABLE[@]} == 0 )); then
    err "No serial devices found. Specify -p manually."
  fi
  echo "Available ports:"; i=1; for p in "${SELECTABLE[@]}"; do echo "  $i) $p"; ((i++)); done
  read -rp "Select port [1-${#SELECTABLE[@]}]: " choice
  if ! [[ $choice =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#SELECTABLE[@]} )); then
    err "Invalid selection"
  fi
  PORT="${SELECTABLE[$((choice-1))]}"
fi

log "Flashing $HEX_FILE_ABS to $PART via $PROGRAMMER on $PORT @ $BAUD"
CMD=(avrdude -p "$PART" -c "$PROGRAMMER" -P "$PORT" -b "$BAUD" -U "flash:w:$HEX_FILE_ABS:i")
if [[ -n "$EXTRA_ARGS" ]]; then
  # shellcheck disable=SC2206
  EXTRA_SPLIT=($EXTRA_ARGS)
  CMD+=("${EXTRA_SPLIT[@]}")
fi

log "Command: ${CMD[*]}"
"${CMD[@]}"

log "Done."
