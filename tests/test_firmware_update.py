"""Updater safety tests; all drives and writes are simulated."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools.bin_to_uf2 import convert
from tools import firmware_update as fw


def edited(data, offset, value):
    result = bytearray(data)
    struct.pack_into('<I', result, offset, value)
    return bytes(result)


class ValidationTests(unittest.TestCase):
    def test_valid_image_has_immutable_data_and_summary(self):
        data = convert(bytes(512))
        image = fw.validate_uf2(data)
        self.assertEqual(image.blocks, 2)
        self.assertEqual((image.start_address, image.end_address), (0x10000000, 0x10000200))
        self.assertEqual(image.data, data)
        self.assertEqual(len(image.sha256), 64)

    def test_rejects_invalid_structure_family_flags_and_payload(self):
        good = convert(bytes(512))
        for offset, value in [(0, 0), (4, 0), (508, 0), (28, 0), (8, 0),
                              (8, 0x2001), (16, 0), (16, 477), (24, 3),
                              (512 + 24, 3), (512 + 20, 0), (20, 2)]:
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                fw.validate_uf2(edited(good, offset, value))
        for bad in [b'', good[:-1], good[:512]]:
            with self.assertRaises(ValueError):
                fw.validate_uf2(bad)

    def test_rejects_overlap_gaps_unaligned_and_configuration_addresses(self):
        good = convert(bytes(512))
        for offset, address in [(12, 0x10000004), (12, 0x0FFFFF00),
                                (12, 0x101FE000), (512 + 12, 0x10000000),
                                (512 + 12, 0x10000300), (512 + 12, 0xFFFFFF00)]:
            with self.subTest(address=address), self.assertRaises(ValueError):
                fw.validate_uf2(edited(good, offset, address))

    def test_ordered_block_numbers_may_arrive_out_of_order(self):
        data = convert(bytes(512))
        self.assertEqual(fw.validate_uf2(data[512:] + data[:512]).blocks, 2)


class DriveTests(unittest.TestCase):
    def test_info_requires_exact_rp2350_board_id(self):
        for text, expected in [('UF2 Bootloader v1\nModel: Raspberry Pi RP2350\nBoard-ID: RP2350\n', True),
                               ('Board-ID: RPI-RP2\n', False), ('Board-ID: RP2350-FAKE\n', False),
                               ('Model: RP2350\n', False)]:
            self.assertEqual(fw.is_rp2350_info(text), expected)

    def test_auto_excludes_existing_manual_accepts_unique_and_multiple_refused(self):
        a = fw.BootDrive('A:/', 'vol-a')
        b = fw.BootDrive('B:/', 'vol-b')
        self.assertIsNone(fw.select_boot_drive([a], [a], manual=False))
        self.assertEqual(fw.select_boot_drive([a, b], [a], manual=False), b)
        self.assertEqual(fw.select_boot_drive([a], [a], manual=True), a)
        for manual in (False, True):
            with self.assertRaises(ValueError):
                fw.select_boot_drive([a, b], [], manual=manual)

    def test_existing_volume_with_changed_drive_letter_is_not_a_new_board(self):
        before = fw.BootDrive('A:/', 'same-volume')
        after = fw.BootDrive('B:/', 'same-volume')
        self.assertIsNone(fw.select_boot_drive([after], [before], manual=False))

    def test_cancel_and_changed_identity_prevent_any_copy(self):
        drive = fw.BootDrive('A:/', 'old')
        writes = []
        updater = fw.FirmwareUpdater(drive_provider=lambda: [drive],
                                     writer=lambda *args: writes.append(args), timeout=0.02)
        image = fw.validate_uf2(convert(bytes(512)))
        with self.assertRaises(fw.UpgradeCancelled):
            updater.transfer(image, [], manual=False, cancelled=lambda: True)
        self.assertEqual(writes, [])
        snapshots = iter([[drive], [fw.BootDrive('A:/', 'replacement')]])
        updater = fw.FirmwareUpdater(drive_provider=lambda: next(snapshots),
                                     writer=lambda *args: writes.append(args))
        with self.assertRaisesRegex(ValueError, 'identity'):
            updater.transfer(image, [], manual=False)
        self.assertEqual(writes, [])

    def test_transfer_writes_once_and_reports_waiting_then_copying(self):
        drive = fw.BootDrive('A:/', 'a')
        writes, stages = [], []
        image = fw.validate_uf2(convert(bytes(512)))
        updater = fw.FirmwareUpdater(drive_provider=lambda: [drive],
                                     writer=lambda d, data, progress: (writes.append((d, data)), progress(100)))
        updater.transfer(image, [], manual=False, changed=lambda stage, progress: stages.append((stage, progress)))
        self.assertEqual(writes, [(drive, image.data)])
        self.assertEqual(stages[0][0], 'waiting_drive')
        self.assertEqual(stages[-1], ('copying', 100))

    def test_second_drive_appearing_before_copy_aborts(self):
        a, b = fw.BootDrive('A:/', 'a'), fw.BootDrive('B:/', 'b')
        snapshots = iter([[a], [a, b]])
        updater = fw.FirmwareUpdater(drive_provider=lambda: next(snapshots),
                                     writer=lambda *args: self.fail('ambiguous write'))
        with self.assertRaises(ValueError):
            updater.transfer(fw.validate_uf2(convert(bytes(256))), [], manual=False)

    def test_prepare_reads_file_once_and_transfer_uses_validated_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'image.uf2'
            data = convert(bytes(512))
            path.write_bytes(data)
            updater = fw.FirmwareUpdater(drive_provider=lambda: [fw.BootDrive('A:/', 'a')],
                                         writer=lambda d, payload, p: self.assertEqual(payload, data))
            image = updater.prepare(path)
            path.write_bytes(b'changed')
            updater.transfer(image, [], manual=True)

    def test_default_writer_flushes_complete_validated_file_to_fake_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            drive = fw.BootDrive(tmp, 'temporary-test-directory', volume_root=tmp)
            data = convert(bytes(40000))
            updater = fw.FirmwareUpdater(drive_provider=lambda: [drive])
            stages = []
            updater.transfer(fw.validate_uf2(data), [], manual=True,
                             changed=lambda stage, progress: stages.append((stage, progress)))
            self.assertEqual((Path(tmp) / 'PEDALS.UF2').read_bytes(), data)
            self.assertEqual(stages[-1], ('copying', 100))

    def test_writer_uses_captured_volume_instead_of_reassigned_drive_letter(self):
        with tempfile.TemporaryDirectory() as original, tempfile.TemporaryDirectory() as replacement:
            # Both locations exist at open time, just like a reassigned drive
            # letter. The bytes must go through the captured volume path.
            drive = fw.BootDrive(replacement, 'captured-volume', volume_root=original)
            data = convert(bytes(256))
            fw._write_image(drive, data, lambda progress: None)
            self.assertEqual((Path(original) / 'PEDALS.UF2').read_bytes(), data)
            self.assertFalse((Path(replacement) / 'PEDALS.UF2').exists())

    def test_writer_refuses_drive_letter_fallback_without_volume_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'volume'):
                fw._write_image(fw.BootDrive(tmp, 'missing-volume'), convert(bytes(256)), lambda _: None)
            self.assertFalse((Path(tmp) / 'PEDALS.UF2').exists())

    def test_drive_timeout_never_writes(self):
        updater = fw.FirmwareUpdater(drive_provider=lambda: [], timeout=0.001, poll_interval=0.001,
                                     writer=lambda *args: self.fail('unexpected write'))
        with self.assertRaises(TimeoutError):
            updater.transfer(fw.validate_uf2(convert(bytes(256))), [], manual=False)


if __name__ == '__main__':
    unittest.main()
