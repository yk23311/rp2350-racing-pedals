"""Mechanical invariants from the original Waveshare dimension drawing."""
import unittest

from tools.hardware.board_geometry import module_pads, mounting_holes, receiver_keepout


class CarrierGeometryTests(unittest.TestCase):
    def test_module_pin_numbers_follow_actual_perimeter_not_pico_order(self):
        pads = module_pads()
        self.assertEqual(set(pads), {str(n) for n in range(1, 19)})
        self.assertEqual(pads['1'], (2.88, 1.13))  # GP0, Type-C end
        self.assertEqual(pads['9'], (23.2, 1.13))  # GP8, USB-A end
        self.assertEqual(pads['18'], (2.88, 16.37))  # VSYS
        self.assertEqual(pads['17'], (5.42, 16.37))  # GND
        self.assertEqual(pads['16'], (7.96, 16.37))  # 3V3
        self.assertEqual(pads['12'], (18.12, 16.37))  # GP26 throttle
        self.assertEqual(pads['13'], (15.58, 16.37))  # GP27 brake
        self.assertAlmostEqual(pads['18'][1] - pads['1'][1], 15.24)

    def test_four_mounts_leave_room_for_m3_hardware(self):
        holes = mounting_holes()
        self.assertEqual(len(set(holes)), 4)
        for x, y in holes:
            self.assertTrue(3.5 <= x <= 96.5)
            self.assertTrue(3.5 <= y <= 76.5)

    def test_receiver_clearance_is_a_component_keepout_in_board(self):
        x0, y0, x1, y1 = receiver_keepout()
        self.assertGreater(x1 - x0, 35)
        self.assertGreater(y1 - y0, 15)
        self.assertTrue(0 <= x0 < x1 <= 100)
        self.assertTrue(0 <= y0 < y1 <= 80)


if __name__ == '__main__':
    unittest.main()
