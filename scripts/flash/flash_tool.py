#!/usr/bin/env python3
"""Unified Flash Tool for OpenEVSE Project

Replaces separate shell/batch scripts with a cross-platform Python CLI.

Subcommands:
  esp     Flash ESP32 firmware (bin/elf + optional bootloader/partitions/fs)
  lgt     Flash LGT8F328P (Arduino-compatible AVR derivative) via avrdude
  both    Flash ESP32 first, then LGT8F328P using one workflow

Key Features:
  * Autodetect firmware/hex files if not specified
  * Autodetect serial ports (interactive selection if multiple)
  * Optional non-interactive mode for CI
  * Virtual environment bootstrap helper (--bootstrap) to install deps
  * File pattern selection and confirmation prompts

Dependencies:
  * esptool (for ESP32)
  * pyserial (optional: only for user serial miniterm advice)
  * avrdude (external executable) for LGT8F328P (must be installed separately)

Examples:
  python scripts/flash/flash_tool.py esp --port /dev/ttyUSB0
  python scripts/flash/flash_tool.py esp --file build/firmware.elf --erase
  python scripts/flash/flash_tool.py lgt --hex build/open_evse.ino.hex --port /dev/ttyUSB1
  python scripts/flash/flash_tool.py both --esp-file build/firmware.bin --lgt-hex build/open_evse.ino.hex
  python scripts/flash/flash_tool.py --bootstrap  # create .venv and install deps
"""
from __future__ import annotations
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import re

# ------------------------------- Common Helpers ------------------------------

def run_cmd(cmd: list[str] | str, check: bool = True):
    print("[CMD]", cmd if isinstance(cmd, str) else " ".join(cmd))
    if isinstance(cmd, str):
        result = subprocess.run(cmd, shell=True)
    else:
        result = subprocess.run(cmd)
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


def which(name: str) -> str | None:
    return shutil.which(name)


def ensure_esptool() -> str:
    # prefer esptool.py directly
    if which("esptool.py"):
        return "esptool.py"
    try:
        subprocess.run([sys.executable, "-m", "esptool", "version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"{sys.executable} -m esptool"
    except Exception:
        print("[ERROR] esptool not installed.")
        print("Hint: bootstrap and activate the local virtual environment:")
        print("  python scripts/flash/flash_tool.py --bootstrap")
        print("Then activate it:")
        print("  Linux/macOS:   source .venv/bin/activate")
        print("  Windows (cmd): .\\.venv\\Scripts\\activate.bat")
        print("  Windows (PS):  .\\.venv\\Scripts\\Activate.ps1")
        print("After activation, re-run this command.")
        sys.exit(1)


def bootstrap_environment(force: bool = False):
    venv_dir = Path('.venv')
    if force and venv_dir.exists():
        print('[+] Removing existing .venv (force)')
        shutil.rmtree(venv_dir)
    if not venv_dir.exists():
        print('[+] Creating virtual environment (.venv)')
        run_cmd([sys.executable, '-m', 'venv', '.venv'])
    # Activate by using path explicit pip
    pip_path = venv_dir / ('Scripts/pip.exe' if platform.system().lower() == 'windows' else 'bin/pip')
    if not pip_path.exists():
        print('[ERROR] pip not found inside venv')
        sys.exit(1)
    print('[+] Upgrading pip & installing dependencies (esptool pyserial)')
    run_cmd([str(pip_path), 'install', '--upgrade', 'pip', 'setuptools', 'wheel'])
    run_cmd([str(pip_path), 'install', '--upgrade', 'esptool', 'pyserial'])
    print('[+] Bootstrap complete.')
    print('Activate the environment before flashing:')
    print('  Linux/macOS:   source .venv/bin/activate')
    print('  Windows (cmd): .\\.venv\\Scripts\\activate.bat')
    print('  Windows (PS):  .\\.venv\\Scripts\\Activate.ps1')
    print('Then run: python scripts/flash/flash_tool.py esp (or lgt/both) ...')


# ------------------------------- Port Detection ------------------------------

def detect_ports() -> list[str]:
    system = platform.system().lower()
    ports: list[str] = []
    if 'windows' in system:
        try:
            out = subprocess.check_output(['wmic', 'path', 'Win32_SerialPort', 'get', 'DeviceID'], stderr=subprocess.DEVNULL).decode(errors='ignore')
            ports = [l.strip() for l in out.splitlines() if l.strip().startswith('COM')]
        except Exception:
            ports = []
    else:
        import glob
        for pattern in ('/dev/ttyUSB*', '/dev/ttyACM*', '/dev/cu.usbserial*', '/dev/cu.*'):
            for p in glob.glob(pattern):
                if os.path.exists(p):
                    ports.append(p)
    return sorted(set(ports))


def choose_port(provided: str | None, non_interactive: bool) -> str:
    if provided:
        return provided
    ports = detect_ports()
    if not ports:
        if non_interactive:
            print('[ERROR] No ports detected and none specified.')
            sys.exit(2)
        return input('Enter serial port (e.g. COM5 or /dev/ttyUSB0): ').strip()
    if len(ports) == 1:
        if non_interactive:
            return ports[0]
        ans = input(f"Detected single port '{ports[0]}'. Use this? [Y/n]: ").strip().lower() or 'y'
        return ports[0] if ans in ('y','yes') else input('Enter serial port: ').strip()
    if non_interactive:
        print('[ERROR] Multiple ports detected; specify --port.')
        sys.exit(2)
    print('Available ports:')
    for i,p in enumerate(ports,1):
        print(f'  {i}) {p}')
    sel = input(f'Select [1-{len(ports)}] or enter custom: ').strip()
    if sel.isdigit() and 1 <= int(sel) <= len(ports):
        return ports[int(sel)-1]
    return sel

# ------------------------------- ESP32 Flashing ------------------------------
ESP_APP_OFFSET = 0x10000
ESP_BOOTLOADER_OFFSET = 0x1000
ESP_PARTITIONS_OFFSET = 0x8000
ESP_BOOT_APP0_OFFSET = 0xE000
PARTITION_FS_PATTERN = re.compile(r"^(spiffs|littlefs),", re.IGNORECASE)

def autodetect_esp_firmware(non_interactive: bool, user: str | None) -> Path:
    if user:
        return Path(user)
    cwd = Path.cwd()
    bin_candidates = sorted(cwd.glob('firmware*.bin')) or sorted(cwd.glob('*.bin'))
    elf_candidates = sorted(cwd.glob('*.elf'))
    # Filter out known non-app pieces
    filtered = [c for c in (bin_candidates + elf_candidates) if c.name not in ('bootloader.bin','partitions.bin','boot_app0.bin')]
    if not filtered:
        if non_interactive:
            print('[ERROR] No firmware found and --file not specified.')
            sys.exit(2)
        return Path(input('Enter path to firmware (.bin/.elf): ').strip())
    if len(filtered) == 1:
        if non_interactive:
            return filtered[0]
        ans = input(f"Use firmware '{filtered[0].name}'? [Y/n]: ").strip().lower() or 'y'
        return filtered[0] if ans in ('y','yes') else Path(input('Enter path to firmware: ').strip())
    if non_interactive:
        print('[ERROR] Multiple firmware candidates; specify --file.')
        for f in filtered: print('  -', f)
        sys.exit(2)
    print('Firmware candidates:')
    for i,f in enumerate(filtered,1):
        print(f'  {i}) {f.name}')
    sel = input(f'Select [1-{len(filtered)}] or enter custom: ').strip()
    if sel.isdigit() and 1 <= int(sel) <= len(filtered):
        return filtered[int(sel)-1]
    return Path(sel)


def convert_elf_to_bin(esptool_cmd: str, elf: Path) -> Path:
    out_dir = Path(tempfile.mkdtemp(prefix='espconv_'))
    out_base = out_dir / 'firmware'
    cmd = f"{esptool_cmd} --chip esp32 elf2image -o {out_base} {elf}" if isinstance(esptool_cmd,str) else esptool_cmd
    run_cmd(cmd)
    bins = list(out_dir.glob('firmware*.bin'))
    if not bins:
        print('[ERROR] elf2image produced no .bin')
        sys.exit(3)
    primary = out_dir / 'firmware.bin'
    return primary if primary.exists() else bins[0]


def parse_partitions_for_fs(csv_path: Path):
    try:
        with csv_path.open('r', encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith('#'): continue
                parts=[c.strip() for c in line.split(',')]
                if len(parts) < 5: continue
                name, _type, _sub, offset, _size = parts[:5]
                if PARTITION_FS_PATTERN.match(name):
                    try: return int(offset,0)
                    except ValueError: continue
    except Exception:
        return None
    return None


def build_esp_flash_cmds(esptool_cmd: str, port: str, baud: int, mode: str, bootloader: Path|None, partitions: Path|None, boot_app0: Path|None, app_bin: Path, erase: bool, fs_image: Path|None, fs_offset: int|None) -> list[list[str]]:
    base = esptool_cmd.split() if isinstance(esptool_cmd,str) else [esptool_cmd]
    base += ['--chip','esp32','--port',port,'--baud',str(baud)]
    commands: list[list[str]] = []
    if erase:
        commands.append(base + ['erase_flash'])
    flash = base + ['write_flash','-z']
    if mode=='full' and bootloader and partitions:
        flash += [f'0x{ESP_BOOTLOADER_OFFSET:05X}', str(bootloader), f'0x{ESP_PARTITIONS_OFFSET:05X}', str(partitions)]
        if boot_app0:
            flash += [f'0x{ESP_BOOT_APP0_OFFSET:05X}', str(boot_app0)]
    flash += [f'0x{ESP_APP_OFFSET:05X}', str(app_bin)]
    if fs_image and fs_offset is not None:
        flash += [f'0x{fs_offset:05X}', str(fs_image)]
    commands.append(flash)
    return commands


def flash_esp(args):
    esptool_cmd = ensure_esptool()
    firmware_path = autodetect_esp_firmware(args.non_interactive, args.file)
    if not firmware_path.exists():
        print(f"[ERROR] Firmware not found: {firmware_path}")
        sys.exit(2)
    port = choose_port(args.port, args.non_interactive)
    working_bin = firmware_path
    if firmware_path.suffix.lower()=='.elf':
        print('[+] Converting ELF to BIN ...')
        working_bin = convert_elf_to_bin(esptool_cmd, firmware_path)
        print('[+] Generated BIN:', working_bin)
    # Companion files
    d = working_bin.parent
    bootloader = (d/'bootloader.bin') if (d/'bootloader.bin').exists() else None
    partitions = (d/'partitions.bin') if (d/'partitions.bin').exists() else None
    boot_app0 = (d/'boot_app0.bin') if (d/'boot_app0.bin').exists() else None
    mode = 'full' if bootloader and partitions and not args.no_full else 'app'
    # FS image
    fs_image = None; fs_offset=None
    for pat in ('*spiffs*.bin','*littlefs*.bin'):
        matches = list(d.glob(pat))
        if matches:
            fs_image = matches[0]
            break
    if args.filesystem:
        candidate = Path(args.filesystem)
        if candidate.exists(): fs_image = candidate
    if fs_image:
        csv = d/'partitions.csv'
        if args.partitions_csv:
            csv = Path(args.partitions_csv)
        if csv.exists():
            fs_offset = parse_partitions_for_fs(csv)
        if fs_offset is None:
            print('[WARN] Could not determine filesystem offset; skipping FS image')
            fs_image=None
    print('\n=== ESP32 Flash Plan ===')
    print('Mode:', mode)
    print('Port:', port)
    print('Baud:', args.baud)
    print('App :', working_bin, '@', hex(ESP_APP_OFFSET))
    if mode=='full':
        print('Bootloader :', bootloader)
        print('Partitions :', partitions)
        print('boot_app0  :', boot_app0)
    if fs_image:
        print('FS Image   :', fs_image, '@', hex(fs_offset or 0))
    if args.erase:
        print('Erase flash: YES')
    if not args.non_interactive:
        cont=input('Proceed? [y/N]: ').strip().lower()
        if cont not in ('y','yes'):
            print('Aborted.')
            return
    for c in build_esp_flash_cmds(esptool_cmd, port, args.baud, mode, bootloader, partitions, boot_app0, working_bin, args.erase, fs_image, fs_offset):
        run_cmd(c)
    print('[+] ESP32 flash complete.')

# ------------------------------- LGT Flashing --------------------------------

def which_avrdude() -> str:
    avrdude = which('avrdude')
    if not avrdude:
        print('[ERROR] avrdude not in PATH. Install (Linux: apt/dnf/pacman, macOS: brew install avrdude, Windows: Arduino IDE/WinAVR).')
        sys.exit(1)
    return avrdude


def autodetect_hex(non_interactive: bool, user: str | None) -> Path:
    if user:
        return Path(user)
    detected = sorted(Path.cwd().glob('*.hex'))
    if not detected:
        if non_interactive:
            print('[ERROR] No HEX file and --hex missing.')
            sys.exit(2)
        return Path(input('Enter HEX file path: ').strip())
    if len(detected)==1:
        if non_interactive:
            return detected[0]
        ans=input(f"Use HEX '{detected[0].name}'? [Y/n]: ").strip().lower() or 'y'
        return detected[0] if ans in ('y','yes') else Path(input('Enter HEX file: ').strip())
    if non_interactive:
        print('[ERROR] Multiple HEX files; specify --hex.')
        for f in detected: print('  -', f)
        sys.exit(2)
    print('HEX candidates:')
    for i,f in enumerate(detected,1):
        print(f'  {i}) {f.name}')
    sel = input(f'Select [1-{len(detected)}] or custom: ').strip()
    if sel.isdigit() and 1 <= int(sel) <= len(detected):
        return detected[int(sel)-1]
    return Path(sel)


def flash_lgt(args):
    avrdude = which_avrdude()
    hex_file = autodetect_hex(args.non_interactive, args.hex)
    if not hex_file.exists():
        print('[ERROR] HEX file not found:', hex_file)
        sys.exit(2)
    port = choose_port(args.port, args.non_interactive)
    cmd = [avrdude, '-p', args.part, '-c', args.programmer, '-P', port, '-b', str(args.baud), '-U', f'flash:w:{hex_file}:i']
    if args.extra:
        cmd.extend(args.extra)
    print('\n=== LGT8F328P Flash Plan ===')
    print('Port:', port)
    print('Baud:', args.baud)
    print('HEX :', hex_file)
    print('Part:', args.part)
    print('Prog:', args.programmer)
    if not args.non_interactive:
        cont=input('Proceed? [y/N]: ').strip().lower()
        if cont not in ('y','yes'):
            print('Aborted.')
            return
    run_cmd(cmd)
    print('[+] LGT flash complete.')

# ------------------------------- Combined ------------------------------------

def flash_both(args):
    # Reuse namespace but with esp- prefixed args
    esp_args = argparse.Namespace(
        file=args.esp_file,
        port=args.esp_port,
        baud=args.esp_baud,
        erase=args.esp_erase,
        no_full=args.esp_no_full,
        filesystem=args.esp_filesystem,
        partitions_csv=args.esp_partitions_csv,
        chip='esp32',
        non_interactive=args.non_interactive
    )
    flash_esp(esp_args)
    lgt_args = argparse.Namespace(
        hex=args.lgt_hex,
        port=args.lgt_port,
        baud=args.lgt_baud,
        programmer=args.lgt_programmer,
        part=args.lgt_part,
        extra=args.lgt_extra,
        non_interactive=args.non_interactive
    )
    flash_lgt(lgt_args)

# ------------------------------- Argument Parsing ----------------------------

def build_parser():
    p = argparse.ArgumentParser(description='Unified OpenEVSE Flash Tool')
    p.add_argument('--bootstrap', action='store_true', help='Create/upgrade local .venv and install core deps (esptool, pyserial). Exits after completion.')
    p.add_argument('--force-bootstrap', action='store_true', help='Recreate .venv from scratch before bootstrapping')
    p.add_argument('--non-interactive', '-y', action='store_true', help='Fail instead of prompting for choices')
    sub = p.add_subparsers(dest='command', required=False)

    # ESP subcommand
    pe = sub.add_parser('esp', help='Flash ESP32 firmware')
    pe.add_argument('--file','-f', help='Firmware file (.bin/.elf)')
    pe.add_argument('--port','-p', help='Serial port')
    pe.add_argument('--baud','-b', type=int, default=921600)
    pe.add_argument('--erase', action='store_true')
    pe.add_argument('--no-full', action='store_true', help='Do not flash bootloader/partitions even if present')
    pe.add_argument('--filesystem')
    pe.add_argument('--partitions-csv')

    # LGT subcommand
    pl = sub.add_parser('lgt', help='Flash LGT8F328P (avrdude)')
    pl.add_argument('--hex','-H', help='HEX file')
    pl.add_argument('--port','-p', help='Serial/programmer port')
    pl.add_argument('--baud','-b', type=int, default=115200)
    pl.add_argument('--programmer','-P', default='avrisp')
    pl.add_argument('--part', default='lgt8f328p')
    pl.add_argument('--extra', nargs='*', default=[])

    # BOTH subcommand
    pb = sub.add_parser('both', help='Flash ESP32 then LGT8F328P')
    pb.add_argument('--esp-file')
    pb.add_argument('--esp-port')
    pb.add_argument('--esp-baud', type=int, default=921600)
    pb.add_argument('--esp-erase', action='store_true')
    pb.add_argument('--esp-no-full', action='store_true')
    pb.add_argument('--esp-filesystem')
    pb.add_argument('--esp-partitions-csv')
    pb.add_argument('--lgt-hex')
    pb.add_argument('--lgt-port')
    pb.add_argument('--lgt-baud', type=int, default=115200)
    pb.add_argument('--lgt-programmer', default='avrisp')
    pb.add_argument('--lgt-part', default='lgt8f328p')
    pb.add_argument('--lgt-extra', nargs='*', default=[])

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.bootstrap:
        bootstrap_environment(force=args.force_bootstrap)
        return
    if not args.command:
        parser.print_help()
        print('\nHint: specify one of: esp | lgt | both')
        return
    if args.command == 'esp':
        flash_esp(args)
    elif args.command == 'lgt':
        flash_lgt(args)
    elif args.command == 'both':
        flash_both(args)
    else:
        parser.error('Unknown command')

if __name__ == '__main__':
    main()
