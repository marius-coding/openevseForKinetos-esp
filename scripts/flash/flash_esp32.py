#!/usr/bin/env python3
"""
OpenEVSE ESP32 Flash Helper

Interactive (or semi-automatic) utility to flash a precompiled firmware image
(.bin or .elf) to an ESP32 using esptool.

Features:
- Accepts either ELF (.elf) or raw application binary (.bin)
  * If an ELF is given, converts to .bin using esptool's elf2image
- Optional full flash sequence when accompanying bootloader/partition/bin files
  are present in the same directory
- Prompts user for serial COM port (Windows style: COM3, etc.)
- Validates addresses & existence of files
- Provides --non-interactive mode via CLI args

Usage examples:
  python flash_esp32.py
  python flash_esp32.py --file build/firmware.elf --port COM5
  python flash_esp32.py --file firmware.bin --port COM4 --baud 921600 --erase

Default flash layout (app-only):
  0x10000 firmware.bin (app)

Full flash layout (if all components found):
  0x1000   bootloader.bin
  0x8000   partitions.bin
  0xE000   boot_app0.bin (optional, only if exists)
  0x10000  firmware.bin
  (Plus filesystem image if partitions table indicates and a *spiffs*.bin or *littlefs*.bin is present. Offset auto-parsed.)

You can override addresses with --addr-* arguments if required.
"""
from __future__ import annotations
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ESPNAME = "esp32"  # base chip name (could extend later)
DEFAULT_APP_OFFSET = 0x10000
DEFAULT_BOOTLOADER_OFFSET = 0x1000
DEFAULT_PARTITIONS_OFFSET = 0x8000
DEFAULT_BOOT_APP0_OFFSET = 0xE000

PARTITION_FS_PATTERN = re.compile(r"^(?P<name>spiffs|littlefs),", re.IGNORECASE)


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def ensure_esptool() -> str:
    if which("esptool.py"):
        return "esptool.py"
    # Fallback: python -m esptool
    try:
        subprocess.run([sys.executable, "-m", "esptool", "version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"{sys.executable} -m esptool"
    except Exception:
        print("[ERROR] esptool not installed. Install with: pip install esptool")
        sys.exit(1)


def run(cmd: list[str] | str):
    print("[CMD]", cmd if isinstance(cmd, str) else " ".join(cmd))
    if isinstance(cmd, str):
        result = subprocess.run(cmd, shell=True)
    else:
        result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[ERROR] Command failed: {result.returncode}")
        sys.exit(result.returncode)


def parse_args():
    p = argparse.ArgumentParser(description="ESP32 Flash Utility for OpenEVSE")
    p.add_argument("--file", "-f", help="Path to firmware .elf or .bin")
    p.add_argument("--root", help="Explicit project root / base directory for resolving relative firmware path (defaults: CWD, script dir, script parent)")
    p.add_argument("--auto-pattern", default="firmware*.bin", help="Pattern to search when --file points to a directory (default: firmware*.bin)")
    p.add_argument("--port", "-p", help="Serial port (e.g. COM5 or /dev/ttyUSB0)")
    p.add_argument("--baud", "-b", type=int, default=921600, help="Baud rate (default 921600)")
    p.add_argument("--erase", action="store_true", help="Erase entire flash before writing")
    p.add_argument("--no-full", action="store_true", help="Force app-only flashing even if other files present")
    p.add_argument("--addr-app", type=lambda x: int(x, 0), help="Override app offset (default 0x10000)")
    p.add_argument("--addr-bootloader", type=lambda x: int(x, 0), help="Override bootloader offset (default 0x1000)")
    p.add_argument("--addr-partitions", type=lambda x: int(x, 0), help="Override partitions offset (default 0x8000)")
    p.add_argument("--addr-bootapp0", type=lambda x: int(x, 0), help="Override boot_app0 offset (default 0xE000)")
    p.add_argument("--non-interactive", action="store_true", help="Fail if required info missing instead of prompting")
    p.add_argument("--filesystem", help="Explicit filesystem image (.bin) to include")
    p.add_argument("--partitions-csv", help="Partitions CSV to parse for FS offset (if including FS)")
    p.add_argument("--chip", default=ESPNAME, help="Chip name passed to esptool (default esp32)")
    return p.parse_args()


def prompt_if_missing(value: str | None, prompt: str, non_interactive: bool) -> str:
    if value:
        return value
    if non_interactive:
        print(f"[ERROR] Missing required: {prompt}")
        sys.exit(2)
    return input(prompt + ": ").strip()


def convert_elf_to_bin(esptool_cmd: str, elf_path: Path) -> Path:
    out_dir = Path(tempfile.mkdtemp(prefix="espflash_"))
    # esptool.py --chip esp32 elf2image -o outdir/ firmware.elf
    out_base = out_dir / "firmware"
    cmd = f"{esptool_cmd} --chip {ESPNAME} elf2image -o {out_base} {elf_path}" if isinstance(esptool_cmd, str) else esptool_cmd
    if isinstance(esptool_cmd, str):
        run(cmd)
    else:
        # Note: this branch is unlikely because ensure_esptool returns a string command
        # but kept for completeness.
        run(cmd + ["--chip", ESPNAME, "elf2image", "-o", str(out_base), str(elf_path)])
    # esptool creates firmware.bin (and optionally firmware-N.bin for multi-segment)
    # Find first .bin
    bins = list(out_dir.glob("firmware*.bin"))
    if not bins:
        print("[ERROR] elf2image did not produce a .bin file")
        sys.exit(3)
    # Prefer the plain firmware.bin
    primary = out_dir / "firmware.bin"
    return primary if primary.exists() else bins[0]


def autodetect_companion_bins(fw_path: Path):
    d = fw_path.parent
    candidates = {
        "bootloader": d / "bootloader.bin",
        "partitions": d / "partitions.bin",
        "boot_app0": d / "boot_app0.bin",
    }
    found = {k: v for k, v in candidates.items() if v.exists()}
    return found


def parse_partition_csv_for_fs_offset(csv_path: Path):
    if not csv_path or not csv_path.exists():
        return None
    try:
        with csv_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [c.strip() for c in line.split(",")]
                if len(parts) < 5:
                    continue
                name, type_, subtype, offset, size = parts[:5]
                if PARTITION_FS_PATTERN.match(name):
                    # offset may be like 0x290000
                    try:
                        return int(offset, 0)
                    except ValueError:
                        continue
    except Exception as e:
        print(f"[WARN] Failed parsing partitions CSV: {e}")
    return None


def format_addr(addr: int) -> str:
    return f"0x{addr:06X}"


def main():
    args = parse_args()
    esptool_cmd = ensure_esptool()

    # --- Resolve firmware path robustly ------------------------------------
    def candidate_dirs():
        script_dir = Path(__file__).resolve().parent
        bases = []
        if args.root:
            bases.append(Path(args.root).expanduser().resolve())
        # Invocation CWD
        try:
            bases.append(Path.cwd())
        except Exception:
            pass
        # Script directory
        bases.append(script_dir)
        # Parent of script directory (assumed repo root)
        bases.append(script_dir.parent)
        # De-duplicate preserving order
        seen = set()
        unique = []
        for b in bases:
            if b not in seen:
                unique.append(b)
                seen.add(b)
        return unique

    # Autodetect firmware if --file not provided and interactive
    fw_input = args.file
    if not fw_input and not args.non_interactive:
        # Look for candidate files in CWD: prefer firmware*.bin then *.elf
        cwd = Path.cwd()
        bin_candidates = sorted(cwd.glob("firmware*.bin")) or sorted(cwd.glob("*.bin"))
        elf_candidates = sorted(cwd.glob("*.elf"))
        chosen = None
        candidates = bin_candidates + elf_candidates
        # Filter out obvious non-firmware (e.g., partitions / bootloader)
        filtered = [c for c in candidates if c.name not in ("bootloader.bin", "partitions.bin", "boot_app0.bin")]
        if len(filtered) == 1:
            ans = input(f"Found firmware file '{filtered[0].name}'. Use this? [Y/n]: ").strip().lower() or 'y'
            if ans in ('y','yes'):
                chosen = filtered[0]
        elif len(filtered) > 1:
            print("Multiple firmware candidates detected:")
            for i, f in enumerate(filtered, 1):
                print(f"  {i}) {f.name}")
            sel = input(f"Select [1-{len(filtered)}] or press Enter to type a path: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(filtered):
                chosen = filtered[int(sel)-1]
        if chosen:
            fw_input = str(chosen)
        if not fw_input:
            fw_input = input("Enter path to firmware (.elf or .bin or directory): ").strip()
    elif not fw_input and args.non_interactive:
        print('[ERROR] --file required in non-interactive mode')
        sys.exit(2)

    def resolve_firmware(user_value: str) -> Path:
        p = Path(user_value).expanduser()
        # Absolute existing path
        if p.is_file():
            return p.resolve()
        # If directory: search pattern
        if p.is_dir():
            matches = sorted(p.glob(args.auto_pattern))
            if matches:
                print(f"[INFO] Selected '{matches[0].name}' from directory '{p}'")
                return matches[0].resolve()
        # Try relative to candidate dirs
        tried = []
        for base in candidate_dirs():
            cand = base / p
            tried.append(str(cand))
            if cand.is_file():
                return cand.resolve()
            if cand.is_dir():
                matches = sorted(cand.glob(args.auto_pattern))
                if matches:
                    print(f"[INFO] Selected '{matches[0].name}' in '{cand}' (pattern {args.auto_pattern})")
                    return matches[0].resolve()
        print("[ERROR] Could not resolve firmware path. Tried:")
        for t in tried:
            print("   -", t)
        print("Hints:")
        print(" * Provide a direct path to a .bin or .elf")
        print(" * Provide a directory containing", args.auto_pattern)
        print(" * Use --root to specify project base")
        sys.exit(2)

    fw_path = resolve_firmware(fw_input)
    print(f"[+] Using firmware file: {fw_path}")

    port = prompt_if_missing(args.port, "Enter serial port (e.g. COM5)", args.non_interactive)

    # Determine if ELF needs conversion
    working_bin = fw_path
    if fw_path.suffix.lower() == ".elf":
        print("[+] Converting ELF to BIN via esptool elf2image...")
        working_bin = convert_elf_to_bin(esptool_cmd, fw_path)
        print(f"[+] Generated BIN: {working_bin}")

    # Autodetect other bins
    companion = autodetect_companion_bins(working_bin)
    full_available = all(k in companion for k in ("bootloader", "partitions"))
    if full_available and not args.no_full:
        mode = "full"
    else:
        mode = "app"

    app_offset = args.addr_app or DEFAULT_APP_OFFSET
    boot_offset = args.addr_bootloader or DEFAULT_BOOTLOADER_OFFSET
    part_offset = args.addr_partitions or DEFAULT_PARTITIONS_OFFSET
    bootapp0_offset = args.addr_bootapp0 or DEFAULT_BOOT_APP0_OFFSET

    filesystem_image = None
    fs_offset = None
    if args.filesystem:
        filesystem_image = Path(args.filesystem).expanduser().resolve()
        if not filesystem_image.exists():
            print(f"[ERROR] Filesystem image not found: {filesystem_image}")
            sys.exit(4)
    # If not explicitly provided, look for spiffs/littlefs bin in same folder
    else:
        for pattern in ("*spiffs*.bin", "*littlefs*.bin"):
            found = list(working_bin.parent.glob(pattern))
            if found:
                filesystem_image = found[0]
                break
    if filesystem_image:
        # Need FS offset from partitions CSV if not overridden
        csv_path = Path(args.partitions_csv) if args.partitions_csv else (working_bin.parent / "partitions.csv")
        if csv_path.exists():
            fs_offset = parse_partition_csv_for_fs_offset(csv_path)
        if fs_offset is None:
            print("[WARN] Could not determine filesystem offset automatically; skipping FS image")
            filesystem_image = None

    print("\n=== Flash Plan ===")
    print(f"Mode: {mode}")
    print(f"Port: {port}")
    print(f"Baud: {args.baud}")
    print(f"App Image: {working_bin} @ {format_addr(app_offset)}")
    if mode == "full":
        print(f"Bootloader: {companion['bootloader']} @ {format_addr(boot_offset)}")
        print(f"Partitions: {companion['partitions']} @ {format_addr(part_offset)}")
        if 'boot_app0' in companion:
            print(f"boot_app0: {companion['boot_app0']} @ {format_addr(bootapp0_offset)}")
    if filesystem_image:
        print(f"Filesystem: {filesystem_image} @ {format_addr(fs_offset)}")
    if args.erase:
        print("Full chip erase: YES")
    print("==================\n")

    if not args.non_interactive:
        cont = input("Proceed with flashing? [y/N]: ").strip().lower()
        if cont not in ("y", "yes"):
            print("Aborted by user.")
            return

    # Build command list
    base = []
    if isinstance(esptool_cmd, str):
        base = esptool_cmd.split()
    else:
        base = [esptool_cmd]

    base += ["--chip", args.chip, "--port", port, "--baud", str(args.baud)]

    if args.erase:
        run(base + ["erase_flash"])  # Erase first

    flash_cmd = base + ["write_flash", "-z"]

    if mode == "full":
        flash_cmd += [
            format_addr(boot_offset), str(companion['bootloader']),
            format_addr(part_offset), str(companion['partitions']),
        ]
        if 'boot_app0' in companion:
            flash_cmd += [format_addr(bootapp0_offset), str(companion['boot_app0'])]
    flash_cmd += [format_addr(app_offset), str(working_bin)]
    if filesystem_image and fs_offset is not None:
        flash_cmd += [format_addr(fs_offset), str(filesystem_image)]

    run(flash_cmd)

    print("\n[+] Flash complete. Attempting reset (toggle EN if no reboot).")
    print("Open a serial terminal (e.g., 'python -m serial.tools.miniterm %s 115200') to view logs." % port)


if __name__ == "__main__":
    main()
