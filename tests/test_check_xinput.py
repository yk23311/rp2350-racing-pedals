import ctypes
import unittest
from tools.check_xinput import Gamepad, State, read_slots

class Api:
    def XInputGetState(self, index, pointer):
        if index != 2: return 1167
        value = pointer._obj
        value.packet = 7
        value.gamepad.left_trigger = 91
        value.gamepad.right_trigger = 203
        return 0

class XInputReaderTests(unittest.TestCase):
    def test_native_windows_abi(self):
        self.assertEqual(ctypes.sizeof(Gamepad), 12)
        self.assertEqual(ctypes.sizeof(State), 16)
    def test_reads_independent_triggers_and_ignores_empty_slots(self):
        self.assertEqual(read_slots(Api()), [{"slot":2,"packet":7,"LT":91,"RT":203,"buttons":0,"LX":0,"LY":0,"RX":0,"RY":0}])

if __name__ == '__main__': unittest.main()
