"""Download pinned build dependencies into this project's deps directory only."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "deps"
ROOT.mkdir(exist_ok=True)

def fetch(url, filename):
    path = ROOT / filename
    if not path.exists():
        print(f"Downloading {filename}", flush=True)
        with urllib.request.urlopen(url, timeout=60) as response, path.with_suffix(".partial").open("wb") as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        path.with_suffix(".partial").replace(path)
    print(filename, hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
    return path

def extract(path, destination=ROOT):
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not (destination / name).resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive path")
        archive.extractall(destination)

sdk = fetch("https://codeload.github.com/raspberrypi/pico-sdk/zip/refs/tags/2.2.0", "pico-sdk-2.2.0.zip")
if not (ROOT / "pico-sdk-2.2.0/pico_sdk_init.cmake").exists():
    extract(sdk)
with urllib.request.urlopen("https://api.github.com/repos/raspberrypi/pico-sdk/contents/lib/tinyusb?ref=2.2.0", timeout=60) as response:
    tiny_sha = json.load(response)["sha"]
tiny = fetch(f"https://codeload.github.com/hathach/tinyusb/zip/{tiny_sha}", f"tinyusb-{tiny_sha}.zip")
tiny_target = ROOT / "pico-sdk-2.2.0/lib/tinyusb"
if not (tiny_target / "src/tusb.h").exists():
    extract(tiny)
    if tiny_target.exists():
        tiny_target.rmdir()
    (ROOT / f"tinyusb-{tiny_sha}").rename(tiny_target)
toolchain_name = "arm-gnu-toolchain-14.3.rel1-mingw-w64-x86_64-arm-none-eabi"
arm = fetch(f"https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu/14.3.rel1/binrel/{toolchain_name}.zip", toolchain_name + ".zip")
if not (ROOT / toolchain_name / "bin/arm-none-eabi-gcc.exe").exists():
    extract(arm, ROOT / toolchain_name)
(ROOT / "versions.json").write_text(json.dumps({"sdk": "2.2.0", "tinyusb": tiny_sha, "arm_gcc": "14.3.rel1"}, indent=2), encoding="utf-8")
print("Dependencies ready", flush=True)
