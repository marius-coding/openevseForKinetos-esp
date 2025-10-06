# Unified Python Flash Tool (ESP32 + LGT8F328P)

This fork adds a single cross‑platform Python CLI that can flash BOTH the ESP32 gateway firmware and the Kinetos EVSE controller MCU (LGT8F328P – ATmega328P compatible) without needing PlatformIO, bash, or batch scripts. It lives at:

`scripts/flash/flash_tool.py`

Use it when you:
* Want the quickest path to put prebuilt binaries on hardware
* Need to reflash both MCUs after a full erase
* Are on Windows/macOS/Linux and prefer one unified workflow
* Are operating in a restricted environment where a full PlatformIO build is slow or blocked

You STILL need PlatformIO for building new firmware binaries from source, but once binaries exist this tool handles deployment.

---
## Key Features
* Automatic Python virtualenv bootstrap (`--bootstrap`)
* Finds firmware automatically (prefers `firmware*.bin`, falls back to any `.bin`, converts a `.elf` if needed)
* Converts ELF → BIN transparently via `esptool.py` if only an ELF is present
* Detects companion ESP32 images (bootloader / partitions / boot_app0) – flashes full image set when available, or app-only if not
* Parses `partitions.csv` to locate and optionally flash a filesystem image (`littlefs.bin` / `spiffs.bin`)
* LGT8F328P: autodetects single or multiple `.hex` files and lets you choose (or picks automatically in non-interactive mode)
* Serial port detection (Windows: COM ports; Linux: `/dev/ttyUSB*` `/dev/ttyACM*`; macOS: `/dev/cu.*`)
* Interactive selection OR fully non-interactive automation (`--non-interactive`)
* Combined flashing mode (`both`) flashes ESP32 first, then LGT8F328P
* Clear venv activation hints if tools are missing

---
## Requirements
Minimum:
* Python 3.8+
* For ESP32 flashing: `esptool==4.x` (installed automatically on `--bootstrap`)
* For LGT8F328P flashing: `avrdude` available on PATH (install via package manager or Arduino toolchain)

Recommended packages (auto-installed during bootstrap):
* `pyserial` – improves port detection reliability

Not required unless you are building from source: PlatformIO / Node / toolchains.

---
## Quick Start (First Use)
From repository root:

```bash
python3 scripts/flash/flash_tool.py --bootstrap esp --port /dev/ttyUSB0
```

If you also want to flash the EVSE controller in the same session and a `.hex` exists:

```bash
python3 scripts/flash/flash_tool.py --bootstrap both
```

After bootstrap, activate the virtual environment for subsequent runs:
* Linux / macOS: `source .venv/bin/activate`
* Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
* Windows CMD: `.\.venv\Scripts\activate.bat`

Then you can just call:
```bash
python scripts/flash/flash_tool.py esp
```

---
## Subcommands
```
esp   – Flash only the ESP32 gateway
lgt   – Flash only the LGT8F328P EVSE controller
both  – Flash ESP32 first then LGT8F328P
```

---
## Common Options
```
--bootstrap          Create/update virtualenv & install deps
--root <dir>         Search root for firmware (defaults to repository root)
--port <device>      Specify serial port explicitly (otherwise auto-detect / prompt)
--lgt-port <device>  Explicit port for LGT when using 'both'
--non-interactive    Fail instead of prompting when ambiguity exists (CI / scripted use)
--force-full         Force full ESP32 image flash even if only app binary changed
--no-fs              Skip filesystem image even if detected
--hex <file.hex>     Manually select LGT8F328P hex (skips autodetect)
```

---
## Examples
Flash ESP32 using auto-detected firmware:
```bash
python scripts/flash/flash_tool.py esp
```

Flash both MCUs non-interactively (e.g. in CI) with explicit ports:
```bash
python scripts/flash/flash_tool.py both --non-interactive --port /dev/ttyUSB0 --lgt-port /dev/ttyUSB1
```

Flash ESP32 from a build directory containing only an ELF:
```bash
python scripts/flash/flash_tool.py esp --root .pio/build/wt32-eth01
```
(Tool converts the ELF to BIN before flashing.)

Skip filesystem image (faster) even if `littlefs.bin` exists:
```bash
python scripts/flash/flash_tool.py esp --no-fs
```

Force a full image flash (bootloader + partitions + app + boot_app0 + fs if present):
```bash
python scripts/flash/flash_tool.py esp --force-full
```

---
## What Gets Flashed (ESP32)
Priority order (if files present under `--root` or adjacent to chosen app binary):
1. `bootloader*.bin` @ 0x1000
2. `partitions*.bin` @ 0x8000 (or partitions.csv parsed layout)
3. `boot_app0*.bin` @ 0xE000
4. App firmware (e.g. `firmware.bin`) @ 0x10000
5. Filesystem image (`littlefs.bin` / `spiffs.bin`) @ parsed offset (if not skipped)

If companion images (1–3) are missing the tool performs an app-only flash to avoid accidental erase of critical regions.

---
## LGT8F328P Notes
* Uses `avrdude` with an Arduino‑compatible protocol (same as ATmega328P boards)
* Baud/part/protocol values are selected automatically for typical LGT8F328P USB‑UART bridges; override logic can be added later if needed
* Verify step is enabled by default when supported by your `avrdude` build

---
## Troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| "esptool not found" | venv not active / deps not installed | Run with `--bootstrap` or activate venv |
| No ports detected | Device not in bootloader / cable issue | Re-enter boot mode (IO0→GND), reconnect USB |
| ELF only, no BIN | Build not yet produced image | Tool converts automatically; ensure PlatformIO build succeeded |
| Multiple BINs found | Ambiguity | Use `--non-interactive` with `--root` narrowed or delete stale builds |
| avrdude: not found | Not installed | Install via package manager (e.g. `sudo apt install avrdude`) |


---
## Safety / Validation
The tool does NOT mass-erase the entire ESP32 flash unless the combination of supplied companion images implies a full layout refresh. App-only flashes preserve existing settings stored in NVS / filesystem. For a clean device reset, manually erase flash with `esptool.py erase_flash` before running the tool (advanced users only).
