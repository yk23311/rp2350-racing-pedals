"""Dimensions in mm from Waveshare RP2350-USB-A-details-9.jpg.

The module is drawn horizontally, Type-C left and USB-A right. Pin numbers
are schematic P1 numbers; they are not GPIO numbers or Pico header numbers.
"""


def module_pads():
    pads = {}
    for index in range(9):
        x = round(2.88 + 2.54 * index, 2)
        pads[str(index + 1)] = (x, 1.13)
        pads[str(18 - index)] = (x, 16.37)
    return pads


def mounting_holes():
    return [(4., 4.), (96., 4.), (4., 76.), (96., 76.)]


def receiver_keepout():
    return (36., 10., 76., 28.)
