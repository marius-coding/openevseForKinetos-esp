#!/usr/bin/env python3
"""LGT8F328P Flash Helper (Cross-platform)

Features:
- Accepts HEX file path (file or directory; will search for *.hex if directory)
- Port selection with auto-detection (Windows COMx, /dev/ttyUSB*, /dev/ttyACM*, /dev/cu.*)
- Attempts to locate avrdude; provides install hints if missing
- Non-interactive mode for scripting/CI
- Extra avrdude args passthrough
- Optional --verify (adds -U flash:v:...:i after write or -v flag) -- default relies on avrdude's internal verification for some configs

Examples:
  python scripts/flash_lgt8f328p.py --hex build/open_evse.ino.hex --port /dev/ttyUSB0
  python scripts/flash_lgt8f328p.py -H build/ --pick-first --baud 57600
  python scripts/flash_lgt8f328p.py -y -H build/ -p COM5

"""
from __future__ import annotations
import argparse
import os
import sys
import shutil
import subprocess
from pathlib import Path
import platform
import re

def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def install_hint():
    system = platform.system().lower()
    if 'linux' in system:
        return "Install: sudo apt install avrdude   OR sudo dnf install avrdude OR sudo pacman -S avrdude"
    if 'darwin' in system:
        return "Install: brew install avrdude"
    if 'windows' in system:
        return "Install Arduino IDE or WinAVR; ensure avrdude.exe is in PATH"
    return "See your OS package manager for avrdude"


def detect_ports():
    system = platform.system().lower()
    patterns = []
    if 'windows' in system:
        # Use mode or wmic fallback
        try:
            out = subprocess.check_output(['wmic', 'path', 'Win32_SerialPort', 'get', 'DeviceID'], stderr=subprocess.DEVNULL).decode(errors='ignore')
            ports = [line.strip() for line in out.splitlines() if line.strip().startswith('COM')]
            return ports
        except Exception:
            # fallback: COM1..COM20 existence not reliable; return empty and rely on manual entry
            return []
    else:
        patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/cu.usbserial*", "/dev/cu.*"]
        import glob
        found = []
        for pat in patterns:
            for p in glob.glob(pat):
                if os.path.exists(p):
                    found.append(p)
        return sorted(set(found))


def choose_port(non_interactive: bool, given: str | None) -> str:
    if given:
        return given
    ports = detect_ports()
    if not ports:
        if non_interactive:
            print("[ERROR] No serial ports detected and --port not provided")
            sys.exit(2)
        return input("Enter port (e.g. COM5 or /dev/ttyUSB0): ").strip()
    if non_interactive and len(ports) == 1:
        return ports[0]
    print("Available ports:")
    for idx, p in enumerate(ports, 1):
        print(f"  {idx}) {p}")
    if non_interactive:
        print("[ERROR] Multiple ports; specify --port")
        sys.exit(2)
    while True:
        choice = input(f"Select [1-{len(ports)}] or enter custom: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice)-1]
        if choice:
            return choice


def resolve_hex(path_str: str, pattern: str, non_interactive: bool) -> Path:
    p = Path(path_str).expanduser()
    if p.is_file():
        return p
    if p.is_dir():
        matches = sorted(p.glob(pattern))
        if not matches:
            print(f"[ERROR] Directory {p} contains no matches for pattern {pattern}")
            sys.exit(3)
        if non_interactive:
            return matches[0]
        print("Matching HEX files:")
        for i, m in enumerate(matches, 1):
            print(f"  {i}) {m.name}")
        choice = input(f"Pick file [1-{len(matches)}] (default 1): ").strip() or "1"
        if not choice.isdigit() or not (1 <= int(choice) <= len(matches)):
            print("Invalid selection")
            sys.exit(3)
        return matches[int(choice)-1]
    print(f"[ERROR] HEX path not found: {p}")
    sys.exit(3)


def build_avrdude_command(avrdude: str, part: str, programmer: str, port: str, baud: int, hex_file: Path, extra: list[str], verify: bool) -> list[str]:
    cmd = [avrdude, '-p', part, '-c', programmer, '-P', port, '-b', str(baud), '-U', f'flash:w:{hex_file}:i']
    if verify:
        # Many avrdude versions auto verify; adding -v increases verbosity.
        cmd.append('-v')
    cmd.extend(extra)
    return cmd


def main():
    ap = argparse.ArgumentParser(description="Flash LGT8F328P using avrdude")
    ap.add_argument('--hex', '-H', help='Path to HEX file or directory')
    ap.add_argument('--pattern', default='*.hex', help='Pattern if --hex points to a directory (default: *.hex)')
    ap.add_argument('--port', '-p', help='Serial/Programmer port (COMx or /dev/tty*)')
    ap.add_argument('--baud', '-b', type=int, default=115200, help='Baud rate (default 115200)')
    ap.add_argument('--programmer', '-P', default='avrisp', help='Programmer id (default avrisp)')
    ap.add_argument('--part', default='lgt8f328p', help='MCU part (default lgt8f328p)')
    ap.add_argument('--extra', nargs='*', default=[], help='Extra avrdude args')
    ap.add_argument('--verify', action='store_true', help='Add -v for verbose/verify')
    ap.add_argument('--non-interactive', '-y', action='store_true', help='Fail instead of prompting')
    args = ap.parse_args()

    if not args.hex:
        if not args.non_interactive:
            # Auto-detect *.hex in current working directory
            detected = sorted(Path.cwd().glob('*.hex'))
            if len(detected) == 1:
                ans = input(f"Found HEX file '{detected[0].name}'. Use this? [Y/n]: ").strip().lower() or 'y'
                if ans in ('y', 'yes'):
                    args.hex = str(detected[0])
            elif len(detected) > 1:
                print('Multiple HEX files detected:')
                for i, f in enumerate(detected, 1):
                    print(f"  {i}) {f.name}")
                pick = input(f'Select [1-{len(detected)}] or press Enter to type path: ').strip()
                if pick.isdigit() and 1 <= int(pick) <= len(detected):
                    args.hex = str(detected[int(pick)-1])
            if not args.hex:
                args.hex = input('Enter HEX file or directory: ').strip()
        else:
            print('[ERROR] --hex required in non-interactive mode')
            sys.exit(1)

    avrdude = which('avrdude')
    if not avrdude:
        print('[WARN] avrdude not found in PATH.')
        print(install_hint())
        if args.non_interactive:
            sys.exit(1)
        cont = input('Continue after installing avrdude? (y/N): ').strip().lower()
        if cont not in ('y', 'yes'):
            sys.exit(1)
        avrdude = which('avrdude')
        if not avrdude:
            print('[ERROR] avrdude still not found.')
            sys.exit(1)

    hex_path = resolve_hex(args.hex, args.pattern, args.non_interactive)
    print(f'[+] Using HEX: {hex_path}')

    port = choose_port(args.non_interactive, args.port)
    print(f'[+] Using Port: {port}')

    cmd = build_avrdude_command(avrdude, args.part, args.programmer, port, args.baud, hex_path, args.extra, args.verify)
    print('[CMD]', ' '.join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f'[ERROR] avrdude failed with exit code {e.returncode}')
        sys.exit(e.returncode)

    print('[+] Flash complete.')

if __name__ == '__main__':
    main()
