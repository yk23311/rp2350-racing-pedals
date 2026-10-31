import struct
import unittest
from tools.bin_to_uf2 import convert

class UF2Tests(unittest.TestCase):
    def test_roundtrip_headers_and_flash_reservation(self):
        source = bytes(range(256)) + b'abc'
        output = convert(source)
        self.assertEqual(len(output), 1024)
        restored = b''
        for index in range(2):
            block = output[index*512:(index+1)*512]
            header = struct.unpack('<8I', block[:32])
            self.assertEqual(header, (0x0A324655,0x9E5D5157,0x2000,0x10000000+index*256,256,index,2,0xE48BFF59))
            self.assertEqual(struct.unpack('<I', block[-4:])[0], 0x0AB16F30)
            restored += block[32:288]
        self.assertEqual(restored[:len(source)], source)
        self.assertEqual(restored[len(source):], b'\x00'*(512-len(source)))
    def test_reject_empty_and_configuration_overlap(self):
        for data in (b'', b'x'*(0x1FE000+1)):
            with self.assertRaises(ValueError): convert(data)

if __name__ == '__main__': unittest.main()
