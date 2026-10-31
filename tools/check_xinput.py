"""Read Windows' built-in XInput API. No emulation, mapping, writes, or drivers."""
import argparse
import ctypes
import json
import os
import time

class Gamepad(ctypes.Structure):
    _fields_ = [("buttons",ctypes.c_uint16), ("left_trigger",ctypes.c_uint8),
                ("right_trigger",ctypes.c_uint8), ("lx",ctypes.c_int16),
                ("ly",ctypes.c_int16), ("rx",ctypes.c_int16), ("ry",ctypes.c_int16)]

class State(ctypes.Structure):
    _fields_ = [("packet",ctypes.c_uint32),("gamepad",Gamepad)]

def read_slots(api):
    found = []
    for slot in range(4):
        value = State()
        result = api.XInputGetState(slot,ctypes.byref(value))
        if result == 1167:
            continue
        if result != 0:
            raise OSError(result,f"XInputGetState failed for slot {slot}")
        g = value.gamepad
        found.append(dict(slot=slot,packet=value.packet,LT=g.left_trigger,RT=g.right_trigger,
                          buttons=g.buttons,LX=g.lx,LY=g.ly,RX=g.rx,RY=g.ry))
    return found

def load_api():
    if os.name != 'nt': raise RuntimeError('This diagnostic is for Windows only')
    path = os.path.join(os.environ['SystemRoot'],'System32','xinput1_4.dll')
    api = ctypes.WinDLL(path)
    api.XInputGetState.argtypes = [ctypes.c_uint32,ctypes.POINTER(State)]
    api.XInputGetState.restype = ctypes.c_uint32
    return api

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=0,help='0: one snapshot; positive: monitor changes')
    parser.add_argument('--timestamps',action='store_true',help='prefix each JSON line with Unix time')
    args = parser.parse_args()
    if not 0 <= args.seconds <= 3600: parser.error('seconds must be 0..3600')
    api = load_api()
    end = time.monotonic() + args.seconds
    previous = None
    while True:
        states = read_slots(api)
        if states != previous:
            line = json.dumps(states)
            print(f"{time.time():.3f} {line}" if args.timestamps else line,flush=True)
            previous = states
        if args.seconds == 0 or time.monotonic() >= end: break
        time.sleep(0.05)

if __name__ == '__main__': main()
