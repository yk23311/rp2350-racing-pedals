"""Strict project UF2 validation and RP2350 ROM-drive transfer.

No serial IO lives here. A completed transfer is not flash readback or proof
that the application booted; Session must reconnect and reread its state.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import struct
import time


FLASH_START = 0x10000000
CONFIG_START = 0x101FE000
FAMILY = 0xE48BFF59
MAX_UF2_SIZE = ((CONFIG_START - FLASH_START) // 256) * 512


@dataclass(frozen=True)
class FirmwareImage:
    data: bytes
    blocks: int
    start_address: int
    end_address: int
    sha256: str


def validate_uf2(data: bytes):
    """Accept this project's contiguous ARM Secure flash-only UF2 format."""
    data = bytes(data)
    if not data or len(data) % 512 or len(data) > MAX_UF2_SIZE:
        raise ValueError('UF2 must contain complete 512-byte blocks within the flash limit')
    count = len(data) // 512
    addresses = {}
    for offset in range(0, len(data), 512):
        m0, m1, flags, address, size, number, total, family = struct.unpack_from('<8I', data, offset)
        end_magic, = struct.unpack_from('<I', data, offset + 508)
        if (m0, m1, end_magic) != (0x0A324655, 0x9E5D5157, 0x0AB16F30):
            raise ValueError('Invalid UF2 magic')
        if flags != 0x2000 or family != FAMILY:
            raise ValueError('UF2 must be RP2350 ARM-S flash data (family 0xE48BFF59)')
        if size != 256:
            raise ValueError('Project UF2 payload must be 256 bytes')
        if total != count or number >= count or number in addresses:
            raise ValueError('UF2 block count/number is inconsistent, duplicated or missing')
        if address % 256 or address < FLASH_START or address + size > CONFIG_START:
            raise ValueError('UF2 address is unaligned or crosses the reserved configuration boundary')
        addresses[number] = address
    for number in range(count):
        if addresses[number] != FLASH_START + number * 256:
            raise ValueError('UF2 addresses must be contiguous from flash start without overlaps or gaps')
    return FirmwareImage(data, count, FLASH_START, FLASH_START + count * 256,
                         hashlib.sha256(data).hexdigest())


@dataclass(frozen=True)
class BootDrive:
    root: str
    identity: str
    volume_root: str | None = None


def is_rp2350_info(text):
    # The ROM default BOARD_ID is exactly RP2350 (RP2350 datasheet, USB
    # white-label defaults). Do not infer the MCU from a volume label/model.
    return re.findall(r'^Board-ID:\s*([^\r\n]+)', text, re.MULTILINE) == ['RP2350']


def discover_boot_drives():
    """Find removable Windows volumes carrying the default RP2350 ROM ID."""
    if os.name != 'nt':
        return []
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetLogicalDrives.restype = wintypes.DWORD
    kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel.GetVolumeNameForVolumeMountPointW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD]
    result = []
    mask = kernel.GetLogicalDrives()
    for index in range(26):
        root = f'{chr(65 + index)}:\\'
        if not (mask & (1 << index)) or kernel.GetDriveTypeW(root) != 2:
            continue
        try:
            # Bounded read from the virtual ROM file, not arbitrary storage.
            with (Path(root) / 'INFO_UF2.TXT').open('rb') as stream:
                info = stream.read(4097)
            if len(info) > 4096 or not is_rp2350_info(info.decode('ascii')):
                continue
            serial = wintypes.DWORD()
            if not kernel.GetVolumeInformationW(root, None, 0, ctypes.byref(serial),
                                                 None, None, None, 0):
                continue
            volume_name = ctypes.create_unicode_buffer(1024)
            if not kernel.GetVolumeNameForVolumeMountPointW(root, volume_name, len(volume_name)):
                continue
            identity = volume_name.value + f':{serial.value:08x}:' + hashlib.sha256(info).hexdigest()
            result.append(BootDrive(root, identity, volume_name.value))
        except (OSError, UnicodeError):
            continue
    return result


def select_boot_drive(current, before, *, manual=False):
    existing = {d.identity for d in before}
    candidates = list(current) if manual else [d for d in current if d.identity not in existing]
    if len(candidates) > 1:
        raise ValueError('Multiple RP2350 boot drives; disconnect other boards before retrying')
    return candidates[0] if candidates else None


class UpgradeCancelled(Exception):
    pass


def _write_image(drive, data, progress):
    # No cancellation inside this function: interrupting a ROM flash transfer
    # is unsafe. Session/GUI prevent closing until this call has returned.
    # Write through the captured \\?\Volume{GUID}\ path, never a drive
    # letter that could be reassigned after the final discovery check.
    if not drive.volume_root:
        raise ValueError('Missing captured volume path; refusing drive-letter fallback')
    destination = Path(drive.volume_root) / 'PEDALS.UF2'
    with destination.open('wb') as stream:
        for offset in range(0, len(data), 64 * 1024):
            chunk = data[offset:offset + 64 * 1024]
            if stream.write(chunk) != len(chunk):
                raise OSError('Incomplete UF2 write')
            progress((offset + len(chunk)) * 100 // len(data))
        stream.flush()
        os.fsync(stream.fileno())


class FirmwareUpdater:
    def __init__(self, *, drive_provider=None, writer=None, timeout=30, poll_interval=0.1):
        self.discover = drive_provider or discover_boot_drives
        self._write = writer or _write_image
        self.timeout = timeout
        self.poll_interval = poll_interval

    def prepare(self, path):
        with Path(path).open('rb') as stream:
            data = stream.read(MAX_UF2_SIZE + 1)
        return validate_uf2(data)

    def transfer(self, image, before, *, manual=False, cancelled=lambda: False,
                 changed=lambda stage, progress: None):
        changed('waiting_drive', 0)
        deadline = time.monotonic() + self.timeout
        while True:
            if cancelled():
                raise UpgradeCancelled('Upgrade cancelled before copy')
            drive = select_boot_drive(self.discover(), before, manual=manual)
            if drive is not None:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('RP2350 boot drive did not appear; use BOOT recovery and retry manually')
            time.sleep(self.poll_interval)
        if cancelled():
            raise UpgradeCancelled('Upgrade cancelled before copy')
        # A reused drive letter is not sufficient identity. Never open a new
        # destination that replaced the selected volume between scan and copy.
        if select_boot_drive(self.discover(), before, manual=manual) != drive:
            raise ValueError('RP2350 boot drive identity changed before copy')
        changed('copying', 0)
        if cancelled():
            raise UpgradeCancelled('Upgrade cancelled before copy')
        self._write(drive, image.data, lambda progress: changed('copying', progress))
        return drive
