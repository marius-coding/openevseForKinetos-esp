#!/usr/bin/env python3
"""
Modbus RTU sniffer using two serial adapters (one for TX line, one for RX line).

- Opens two serial ports and captures data from each direction independently
- Groups bytes into frames using a time-based inactivity threshold between bytes
- Prints each frame as hex with timestamp, direction (TX/RX), and CRC check

Typical usage:
    python3 scripts/modbus_sniffer.py --tx /dev/ttyUSB0 --rx /dev/ttyUSB1 --baud 9600 --parity N --stopbits 1 --bytesize 8

Notes:
- Default frame separation is based on inactivity of 20 ms (configurable via --gap-ms)
- If you wired the USB adapters the other way around, just swap the --tx and --rx arguments
- Requires: pip install pyserial
"""
from __future__ import annotations

import argparse
import datetime as dt
import signal
import sys
import threading
import time
from typing import Optional

try:
    import serial  # type: ignore
except Exception:
    print("Error: pyserial is required. Install with: pip install pyserial", file=sys.stderr)
    raise


def crc16_modbus(data: bytes) -> int:
    """Compute Modbus RTU CRC-16 (poly 0xA001, initial 0xFFFF). Returns 16-bit integer.
    The CRC is appended little-endian in Modbus (low byte first, then high byte).
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def format_ts(ts: float) -> str:
    t = dt.datetime.fromtimestamp(ts)
    return t.strftime("%H:%M:%S.%f")[:-3]  # millisecond resolution


class Ansi:
    ENABLED = sys.stdout.isatty()
    RESET = "\033[0m" if ENABLED else ""
    TX = "\033[92m" if ENABLED else ""  # green
    RX = "\033[94m" if ENABLED else ""  # blue
    WARN = "\033[93m" if ENABLED else ""  # yellow
    ERR = "\033[91m" if ENABLED else ""  # red


print_lock = threading.Lock()
stop_event = threading.Event()


def _serial_parity(par: str):
    par = par.upper()
    if par == 'N':
        return serial.PARITY_NONE
    if par == 'E':
        return serial.PARITY_EVEN
    if par == 'O':
        return serial.PARITY_ODD
    raise ValueError("Unsupported parity, use one of: N, E, O")


def _serial_stopbits(sb: int):
    if sb == 1:
        return serial.STOPBITS_ONE
    if sb == 2:
        return serial.STOPBITS_TWO
    raise ValueError("Unsupported stopbits, use 1 or 2")


def _serial_bytesize(bs: int):
    if bs == 7:
        return serial.SEVENBITS
    if bs == 8:
        return serial.EIGHTBITS
    raise ValueError("Unsupported bytesize, use 7 or 8")


class FramePrinter:
    def __init__(self):
        self._header_printed = False

    def print_frame(self, label: str, is_tx: bool, timestamp: float, data: bytes):
        if not data:
            return
        # Print table header once
        with print_lock:
            if not self._header_printed:
                header = "Time                Dir  Slave Func CRC    Check Data"
                print(header)
                print("-" * len(header))
                self._header_printed = True
        # Parse Modbus RTU fields: [slave][function][data...][CRC lo][CRC hi]
        slave_str = "--"
        func_str = "--"
        data_str = ""
        crc_str = ""
        crc_info = ""

        if len(data) >= 1:
            slave_str = f"0x{data[0]:02X}"
        if len(data) >= 2:
            func_str = f"0x{data[1]:02X}"

        if len(data) >= 4:
            payload = data[2:-2]
            crc_lo = data[-2]
            crc_hi = data[-1]
            given_crc = crc_lo | (crc_hi << 8)  # little-endian: low then high
            calc_crc = crc16_modbus(data[:-2])
            data_str = " ".join(f"{b:02X}" for b in payload) if payload else "-"
            crc_str = f"{crc_lo:02X} {crc_hi:02X}"
            if calc_crc == given_crc:
                crc_info = "OK"
            else:
                crc_info = f"BAD({calc_crc:04X}/{given_crc:04X})"
        else:
            # No full frame; show whatever is available as data and mark CRC as missing
            payload = data[2:] if len(data) > 2 else b""
            data_str = " ".join(f"{b:02X}" for b in payload) if payload else "-"
            crc_str = "--"
            crc_info = "--"

        color = Ansi.TX if is_tx else Ansi.RX
        dir_col = "TX" if is_tx else "RX"
        with print_lock:
            # Tabular row: Time Dir Slave Func CRC Check Data
            print(
                f"{format_ts(timestamp)}  {color}{dir_col:<3}{Ansi.RESET} {slave_str:<5} {func_str:<5} {crc_str:<6} {crc_info:<6} {data_str}"
            )
            sys.stdout.flush()


class SerialSniffer(threading.Thread):
    def __init__(
        self,
        port: str,
        label: str,
        is_tx: bool,
        baudrate: int,
        parity: str,
        stopbits: int,
        bytesize: int,
        frame_timeout_s: float,
        printer: Optional[FramePrinter] = None,
    ):
        super().__init__(daemon=True)
        self.port = port
        self.label = label
        self.is_tx = is_tx
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.frame_timeout_s = frame_timeout_s if frame_timeout_s > 0 else 0.02
        self.printer = printer or FramePrinter()
        self._buf = bytearray()
        self._last_byte_ts = 0.0

    def run(self):
        try:
            ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=_serial_parity(self.parity),
                stopbits=_serial_stopbits(self.stopbits),
                bytesize=_serial_bytesize(self.bytesize),
                timeout=min(0.01, max(0.001, self.frame_timeout_s / 5.0)),
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as e:
            with print_lock:
                print(f"{Ansi.ERR}Failed to open {self.port}: {e}{Ansi.RESET}", file=sys.stderr)
                sys.stderr.flush()
            return

        with print_lock:
            print(
                f"Opened {self.port} as {'TX' if self.is_tx else 'RX'}; baud={self.baudrate} parity={self.parity} stop={self.stopbits} bits={self.bytesize} frame_timeout={self.frame_timeout_s*1000:.2f}ms"
            )
            sys.stdout.flush()

        try:
            while not stop_event.is_set():
                b = ser.read(1)
                now = time.monotonic()
                if b:
                    if not self._buf:
                        self._last_byte_ts = now
                    self._buf.extend(b)
                    self._last_byte_ts = now
                else:
                    if self._buf and (now - self._last_byte_ts) >= self.frame_timeout_s:
                        # Flush a frame after inactivity
                        ts_wall = time.time()
                        data = bytes(self._buf)
                        self._buf.clear()
                        self.printer.print_frame(self.label, self.is_tx, ts_wall, data)
        finally:
            # Flush any remaining buffered data on shutdown
            if self._buf:
                ts_wall = time.time()
                data = bytes(self._buf)
                self._buf.clear()
                self.printer.print_frame(self.label, self.is_tx, ts_wall, data)
            try:
                ser.close()
            except Exception:
                pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Modbus RTU sniffer using two serial ports (one per direction)")
    p.add_argument("--tx", dest="tx_port", default="/dev/ttyUSB0", help="Serial port for ESP32 TX line (ESP32->Meter)")
    p.add_argument("--rx", dest="rx_port", default="/dev/ttyUSB1", help="Serial port for Meter TX line (Meter->ESP32)")
    p.add_argument("--baud", dest="baud", type=int, default=9600, help="Baud rate (default: 9600)")
    p.add_argument("--parity", dest="parity", choices=["N", "E", "O"], default="N", help="Parity (N/E/O), default N")
    p.add_argument("--stopbits", dest="stopbits", type=int, choices=[1, 2], default=1, help="Stop bits (1 or 2), default 1")
    p.add_argument("--bytesize", dest="bytesize", type=int, choices=[7, 8], default=8, help="Data bits (7 or 8), default 8")
    p.add_argument(
        "--gap-ms",
        dest="gap_ms",
        type=float,
        default=20.0,
        help="Frame inactivity timeout in milliseconds for separating frames (default: 20)",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.tx_port == args.rx_port:
        print(f"{Ansi.ERR}TX and RX ports must be different{Ansi.RESET}", file=sys.stderr)
        return 2

    frame_timeout_s = args.gap_ms / 1000.0 if args.gap_ms > 0 else 0.02

    printer = FramePrinter()

    tx_sniffer = SerialSniffer(
        port=args.tx_port,
        label="TX (ESP32->Meter)",
        is_tx=True,
        baudrate=args.baud,
        parity=args.parity,
        stopbits=args.stopbits,
        bytesize=args.bytesize,
        frame_timeout_s=frame_timeout_s,
        printer=printer,
    )
    rx_sniffer = SerialSniffer(
        port=args.rx_port,
        label="RX (Meter->ESP32)",
        is_tx=False,
        baudrate=args.baud,
        parity=args.parity,
        stopbits=args.stopbits,
        bytesize=args.bytesize,
        frame_timeout_s=frame_timeout_s,
        printer=printer,
    )

    def handle_sigint(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    # Start both threads
    tx_sniffer.start()
    rx_sniffer.start()

    try:
        while tx_sniffer.is_alive() or rx_sniffer.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        stop_event.set()

    tx_sniffer.join(timeout=1.0)
    rx_sniffer.join(timeout=1.0)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
