"""Write checksums for a freshly built firmware; never infer hardware validation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("host", "xinput", "hid"), required=True)
    parser.add_argument("--diagnostics", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    artifact = f"pedals-{args.mode}"
    files = {}
    for suffix in ("bin", "elf", "elf.map", "uf2"):
        path = args.output / f"{artifact}.{suffix}"
        data = path.read_bytes()
        files[path.name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    map_text = (args.output / f"{artifact}.elf.map").read_text(encoding="utf-8", errors="replace")
    flash_end = re.search(r"(0x[0-9a-fA-F]+)\s+(?:PROVIDE\s*\(\s*)?__flash_binary_end", map_text)
    if not flash_end:
        raise RuntimeError("Cannot find flash end in linker map")
    if int(flash_end[1], 16) > 0x101FE000:
        raise RuntimeError("Firmware overlaps reserved configuration")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    manifest = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "version": {"host": "0.4.0-control-center", "xinput": "0.2.0-xinput", "hid": "0.1.0-hid"}[args.mode],
        "board": "waveshare_rp2350_usb_a",
        "source_revision": revision,
        "source_dirty": dirty,
        "purpose": "Native XInput bridge, MAX(pedal, pad) triggers" if args.mode == "host" else args.mode,
        "host_diagnostics": args.diagnostics,
        "configuration_format": "PDL2 (256 bytes, migrates PDL1)" if args.mode == "host" else "PDL1 (40 bytes)",
        "flashed": False,
        "board_tested": False,
        "validation_note": "Fresh build only. Previous hardware logs do not validate this exact binary.",
        "flash_end": flash_end[1],
        "configuration_start": "0x101fe000",
        "files": files,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest refreshed: {args.output / 'manifest.json'} (not flashed)")


if __name__ == "__main__":
    main()
