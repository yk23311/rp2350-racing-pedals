"""Package a flash .bin for RP2350 ARM Secure using SDK boot/uf2.h constants.

Only targets this project's flash start and reserved configuration boundary.
Does not sign, flash, or validate hardware compatibility.
"""
import argparse
from pathlib import Path
import struct

def convert(data):
    if not 0 < len(data) <= 0x1FE000:
        raise ValueError("Image must be nonempty and fit before configuration at 0x101FE000")
    blocks = (len(data) + 255) // 256
    result = bytearray()
    for index in range(blocks):
        result += struct.pack("<8I", 0x0A324655, 0x9E5D5157, 0x2000,
                              0x10000000 + index*256, 256, index, blocks, 0xE48BFF59)
        result += data[index*256:(index+1)*256].ljust(476, b"\0")
        result += struct.pack("<I", 0x0AB16F30)
    return bytes(result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_bytes(convert(args.input.read_bytes()))
    print(f"Created {args.output} (RP2350 ARM-S, not flashed)")
