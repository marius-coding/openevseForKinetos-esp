#!/usr/bin/env python3
"""
RAPI Sniffer Script

Sniffs RAPI protocol communication from two serial ports (RX and TX) and prints parsed RAPI commands.

Usage:
    python3 rapi_sniffer.py --rx /dev/ttyUSB0 --tx /dev/ttyUSB1 --baud 115200
"""
import sys
import argparse
import serial
import time

def parse_rapi_line(line):
    """Parse a RAPI line and return command and arguments."""
    if not line.startswith(b'$') or not line.endswith(b'^'):
        return None
    try:
        # Remove $ and ^
        payload = line[1:-1].decode('ascii', errors='replace')
        parts = payload.split(' ')
        cmd = parts[0]
        args = parts[1:]
        return cmd, args
    except Exception as e:
        return None

def main():
    parser = argparse.ArgumentParser(description='RAPI protocol sniffer (RX/TX)')
    parser.add_argument('--rx', help='RX serial port (e.g. /dev/ttyUSB0)')
    parser.add_argument('--tx', help='TX serial port (e.g. /dev/ttyUSB1)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    args = parser.parse_args()

    if not args.rx and not args.tx:
        print("Error: At least one of --rx or --tx must be specified", flush=True)
        sys.exit(1)

    ser_rx = None
    ser_tx = None
    
    try:
        if args.rx:
            ser_rx = serial.Serial(args.rx, args.baud, timeout=0.1)
        if args.tx:
            ser_tx = serial.Serial(args.tx, args.baud, timeout=0.1)
    except Exception as e:
        print(f"Error opening serial ports: {e}", flush=True)
        sys.exit(1)
    
    ports_str = []
    if args.rx:
        ports_str.append(f"RX: {args.rx}")
    if args.tx:
        ports_str.append(f"TX: {args.tx}")
    print(f"Listening on {', '.join(ports_str)} at {args.baud} baud...", flush=True)

    buffer_rx = b''
    buffer_tx = b''
    while True:
        try:
            data_rx = ser_rx.read(256) if ser_rx else b''
            data_tx = ser_tx.read(256) if ser_tx else b''
            if data_rx:
                buffer_rx += data_rx
                while b'$' in buffer_rx and b'^' in buffer_rx:
                    start = buffer_rx.find(b'$')
                    end = buffer_rx.find(b'^', start)
                    if end == -1:
                        break
                    line = buffer_rx[start:end+1]
                    buffer_rx = buffer_rx[end+1:]
                    result = parse_rapi_line(line)
                    if result:
                        cmd, args_ = result
                        print(f"RX -> RAPI Command: {cmd} Args: {args_}", flush=True)
                    else:
                        print(f"RX -> Malformed RAPI: {line}", flush=True)
            if data_tx:
                buffer_tx += data_tx
                while b'$' in buffer_tx and b'^' in buffer_tx:
                    start = buffer_tx.find(b'$')
                    end = buffer_tx.find(b'^', start)
                    if end == -1:
                        break
                    line = buffer_tx[start:end+1]
                    buffer_tx = buffer_tx[end+1:]
                    result = parse_rapi_line(line)
                    if result:
                        cmd, args_ = result
                        print(f"TX -> RAPI Command: {cmd} Args: {args_}", flush=True)
                    else:
                        print(f"TX -> Malformed RAPI: {line}", flush=True)
            if not data_rx and not data_tx:
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Exiting...", flush=True)
            break
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(0.5)

if __name__ == '__main__':
    main()
