"""CDC console client. No device access occurs when imported."""
import argparse
import csv
import json
from pathlib import Path
import time
import secrets

class ProtocolError(RuntimeError):
    pass

class CommandRejected(ProtocolError):
    """A complete ERR reply: the request failed, but the link is synchronized."""
    pass

class Client:
    def __init__(self, link):
        self.link = link

    def synchronize(self, nonce=None):
        nonce = nonce or secrets.token_hex(16)
        if len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
            raise ValueError("Invalid synchronization token")
        command = f"PING {nonce}\n".encode("ascii")
        if self.link.write(command) != len(command):
            raise ProtocolError("Incomplete serial write")
        expected = f'OK {{"sync":"{nonce}"}}\n'.encode("ascii")
        deadline = time.monotonic() + 4
        for _ in range(32):
            raw = self.link.readline(768)
            # A previously submitted USB packet may have no trailing LF. The
            # new random nonce identifies our response even after that prefix.
            if raw.endswith(expected):
                return
            if not raw or time.monotonic() >= deadline:
                break
        raise TimeoutError("Cannot synchronize CDC session; reconnect before retrying")

    def request(self, command):
        if not command or len(command) > 127 or any(ord(c) < 32 or ord(c) > 126 for c in command):
            raise ValueError("Command must be one printable ASCII line, at most 127 characters")
        data = (command + "\n").encode("ascii")
        if self.link.write(data) != len(data):
            raise ProtocolError("Incomplete serial write; reconnect before retrying")
        raw = self.link.readline(768)
        if not raw:
            raise TimeoutError("No response; check Type-C connection and firmware")
        if not raw.endswith(b"\n"):
            raise ProtocolError("Truncated response; reconnect before retrying")
        try:
            response = raw.decode("ascii").strip()
        except UnicodeError as exc:
            raise ProtocolError("Non-ASCII response") from exc
        if response == "OK":
            return None
        if response.startswith("ERR "):
            raise CommandRejected(response)
        if response.startswith("OK "):
            try:
                result = json.loads(response[3:])
            except ValueError as exc:
                raise ProtocolError("Invalid JSON response") from exc
            if isinstance(result, dict):
                return result
        raise ProtocolError("Unexpected response")

    def get(self):
        result = self.request("GET")
        if not isinstance(result, dict) or result.get("protocol") != 1:
            raise ProtocolError("Unsupported firmware protocol")
        return result

def set_command(axis, on, off, gamma, window):
    if any(type(v) is not int for v in (axis, on, off, gamma, window)):
        raise ValueError("Parameters must be integers")
    if axis not in (0, 1) or not 0 <= off < on <= 5000 or not 100 <= gamma <= 400 or not 1 <= window <= 8:
        raise ValueError("Require axis 0/1, 0 <= off < on <= 5000, gamma 100..400, window 1..8")
    return f"SET {axis} {on} {off} {gamma} {window}"

def open_link(port):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("Install dependencies: python -m pip install -r tools/requirements.txt") from exc
    link = serial.Serial(port, 115200, timeout=2, write_timeout=2)
    try:
        link.reset_input_buffer()
        Client(link).synchronize()
    except BaseException:
        link.close()
        raise
    return link

def main():
    parser = argparse.ArgumentParser(description="Dual pedal CDC configuration (Type-C USB)")
    parser.add_argument("--port", required=True, help="e.g. COM5; do not guess another device's port")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("get")
    commands.add_parser("save", help="Explicit flash save; release both pedals first")
    commands.add_parser("defaults", help="Reset RAM config, not flash")
    settings = commands.add_parser("set")
    settings.add_argument("axis", type=int, choices=[0, 1])
    for name in ("on", "off", "gamma", "window"):
        settings.add_argument("--" + name, type=int, required=True)
    mode = commands.add_parser("mode")
    mode.add_argument("mode", choices=["joystick", "keyboard"])
    cal = commands.add_parser("calibrate")
    cal.add_argument("axis", type=int, choices=[0, 1])
    export = commands.add_parser("export")
    export.add_argument("path", type=Path)
    monitor = commands.add_parser("monitor")
    monitor.add_argument("--seconds", type=float, default=60)
    monitor.add_argument("--interval", type=float, default=0.1)
    monitor.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "monitor" and (not 0 < args.seconds <= 86400 or not 0.05 <= args.interval <= 10):
        parser.error("seconds must be 0..86400; interval 0.05..10")
    command = None
    if args.action == "set":
        command = set_command(args.axis, args.on, args.off, args.gamma, args.window)
    try:
        with open_link(args.port) as link:
            client = Client(link)
            if args.action == "get":
                print(json.dumps(client.get(), indent=2))
            elif args.action == "set":
                client.request(command)
            elif args.action in ("save", "defaults"):
                client.request(args.action.upper())
            elif args.action == "mode":
                client.request("MODE " + args.mode.upper())
            elif args.action == "calibrate":
                input("Release the selected pedal fully; press Enter to BEGIN: ")
                client.request(f"CAL {args.axis} BEGIN")
                try:
                    input("Press the selected pedal fully and hold; press Enter to END: ")
                    client.request(f"CAL {args.axis} END")
                except BaseException:
                    client.request(f"CAL {args.axis} CANCEL")
                    raise
                print("Calibration is in RAM. Release both pedals, then use save explicitly.")
            elif args.action == "export":
                with args.path.open("x", encoding="utf-8") as out:
                    json.dump(client.get(), out, indent=2)
                    out.write("\n")
            elif args.action == "monitor":
                with args.output.open("x", newline="", encoding="utf-8") as out:
                    writer = csv.writer(out)
                    writer.writerow(["elapsed_s", "raw0", "raw1", "filtered0", "filtered1", "axis0", "axis1", "armed"])
                    start = time.monotonic()
                    while time.monotonic() - start < args.seconds:
                        state = client.get()
                        writer.writerow([round(time.monotonic()-start, 3), *state["raw"], *state["filtered"], *state["output"], state["armed"]])
                        out.flush()
                        time.sleep(args.interval)
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")

if __name__ == "__main__":
    main()
