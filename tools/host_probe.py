"""Read the RP2350 CDC diagnostic stream without sending commands or mapping input."""
import argparse
import sys
import time

import serial
from serial.tools import list_ports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial port, for example COM8")
    parser.add_argument("--baud", type=int, default=115200, help="USB CDC ignores this value")
    parser.add_argument("--seconds", type=float, default=20, help="0 means run until Ctrl+C")
    parser.add_argument("--output", help="optional text log path")
    parser.add_argument("--timestamps", action="store_true", help="prefix each line with Unix time")
    parser.add_argument("--list", action="store_true", help="list serial ports and exit")
    args = parser.parse_args()
    if args.list:
        for port in list_ports.comports():
            print(f"{port.device}\t{port.description}")
        return 0
    if not args.port:
        parser.error("--port is required unless --list is used")
    if args.seconds < 0 or args.seconds > 3600:
        parser.error("seconds must be 0..3600")
    sink = open(args.output, "w", encoding="utf-8") if args.output else None
    start = time.monotonic()
    try:
        with serial.Serial(args.port, args.baud, timeout=0.2) as port:
            print(f"# reading {args.port}; Ctrl+C to stop", flush=True)
            while args.seconds == 0 or time.monotonic() - start < args.seconds:
                raw = port.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", "replace").rstrip("\r\n")
                if args.timestamps:
                    text = f"{time.time():.3f} {text}"
                print(text, flush=True)
                if sink is not None:
                    sink.write(text + "\n")
                    sink.flush()
    except KeyboardInterrupt:
        pass
    finally:
        if sink is not None:
            sink.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
