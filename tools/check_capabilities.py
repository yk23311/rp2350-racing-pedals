"""Read Windows' XInputGetCapabilities for the connected controller. Read-only, no mapping."""
import ctypes
import os
import sys


class Gamepad(ctypes.Structure):
    _fields_ = [
        ("buttons", ctypes.c_uint16),
        ("left_trigger", ctypes.c_uint8),
        ("right_trigger", ctypes.c_uint8),
        ("lx", ctypes.c_int16),
        ("ly", ctypes.c_int16),
        ("rx", ctypes.c_int16),
        ("ry", ctypes.c_int16),
    ]


class Vibration(ctypes.Structure):
    _fields_ = [
        ("left_motor", ctypes.c_uint16),
        ("right_motor", ctypes.c_uint16),
    ]


class Capabilities(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint8),
        ("sub_type", ctypes.c_uint8),
        ("flags", ctypes.c_uint16),
        ("gamepad", Gamepad),
        ("vibration", Vibration),
    ]


def main():
    if os.name != "nt":
        raise RuntimeError("This diagnostic is for Windows only")
    api = ctypes.WinDLL(os.path.join(os.environ["SystemRoot"], "System32", "xinput1_4.dll"))
    api.XInputGetCapabilities.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(Capabilities)]
    api.XInputGetCapabilities.restype = ctypes.c_uint32
    found = False
    for slot in range(4):
        caps = Capabilities()
        result = api.XInputGetCapabilities(slot, 0, ctypes.byref(caps))
        if result == 1167:
            continue
        if result != 0:
            raise OSError(result, f"XInputGetCapabilities failed for slot {slot}")
        found = True
        print(
            f"slot={slot} type={caps.type} subtype={caps.sub_type} flags=0x{caps.flags:04x} "
            f"buttons=0x{caps.gamepad.buttons:04x} LT={caps.gamepad.left_trigger} "
            f"RT={caps.gamepad.right_trigger} LX={caps.gamepad.lx} LY={caps.gamepad.ly} "
            f"RX={caps.gamepad.rx} RY={caps.gamepad.ry} "
            f"vibL={caps.vibration.left_motor} vibR={caps.vibration.right_motor}"
        )
    if not found:
        print("no XInput controller found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
