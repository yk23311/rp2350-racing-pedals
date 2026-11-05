"""Device checklist and update UI behavior without connected hardware."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
import tempfile
from pathlib import Path
from tools.bin_to_uf2 import convert
from tools.control_test_pages import DeviceTestPage, FirmwareUpdatePage
from PySide6.QtWidgets import QApplication


class TestPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_complete_press_release_and_clear(self):
        page = DeviceTestPage()
        page.update_buttons(1 << 12, True)
        self.assertEqual(page.completed_mask, 0)
        page.update_buttons(0, True)
        self.assertEqual(page.completed_mask, 1 << 12)
        page.clear_button.click()
        self.assertEqual(page.completed_mask, 0)

    def test_gap_breaks_pending_release_and_requires_new_press(self):
        page = DeviceTestPage()
        page.update_buttons(1 << 12, True)
        page.update_buttons(0, False)
        page.update_buttons(0, True)
        self.assertEqual(page.completed_mask, 0)
        page.update_buttons(1 << 12, True)
        page.update_buttons(0, True)
        self.assertEqual(page.completed_mask, 1 << 12)

    def test_all_fourteen_physical_buttons(self):
        page = DeviceTestPage()
        mask = sum(1 << bit for bit in (0,1,2,3,4,5,6,7,8,9,12,13,14,15))
        page.update_buttons(mask, True)
        page.update_buttons(0, True)
        self.assertEqual(page.completed_mask, mask)
        self.assertIn("14 / 14", page.checklist_summary.text())

    def test_rumble_start_guards_and_stop_when_stale(self):
        page = DeviceTestPage()
        commands = []
        page.command_requested.connect(commands.append)
        rumble = dict(available=True, enabled=True, faulted=False)
        page.set_context(True, True, {"rumble_test":1}, rumble)
        page.start_rumble()
        self.assertEqual(commands, ["RUMBLE TEST 64 64 500"])
        page.set_context(True, False, {"rumble_test":1}, rumble)
        page.start_rumble(); page.stop_rumble()
        self.assertEqual(commands[-1], "RUMBLE STOP")
        self.assertEqual(len(commands), 2)
        for caps, status in (({},rumble), ({"rumble_test":1},dict(rumble,faulted=True)),
                             ({"rumble_test":1},dict(rumble,enabled=False))):
            page.set_context(True, True, caps, status)
            self.assertFalse(page.start_button.isEnabled())

    def test_demo_and_busy_never_emit_writes(self):
        for demo, busy in ((True,False), (False,True)):
            page = DeviceTestPage(demo=demo); commands=[]
            page.command_requested.connect(commands.append)
            page.set_context(True,True,{"rumble_test":1},dict(available=True,enabled=True),busy)
            page.start_rumble(); page.stop_rumble()
            self.assertEqual(commands, [])

    def test_running_rumble_shows_chinese_status_and_stale_details(self):
        page=DeviceTestPage()
        status=dict(available=True,enabled=True,faulted=False,testing=True,
                    remaining_ms=250,left=64,right=128,received=32,sent=30,
                    errors=1,pending=True,in_flight=True)
        page.set_context(True,True,{"rumble_test":1},status)
        self.assertIn("正在测试 · 剩余 250 ms",page.rumble_status.text())
        self.assertIn("左马达 25% · 右马达 50%",page.rumble_detail.text())
        self.assertIn("游戏命令 32 · USB 已完成 30 · 错误 1",page.rumble_detail.text())
        self.assertIn("待发送 · 传输中",page.rumble_detail.text())
        self.assertNotIn("in_flight",page.rumble_detail.text())
        self.assertIn("in_flight",page.rumble_detail.toolTip())
        page.set_context(True,False,{"rumble_test":1},status)
        self.assertIn("最近一次",page.rumble_detail.text())
        self.assertNotIn("左马达",page.rumble_detail.text())
        self.assertNotIn("正在测试",page.rumble_status.text())

    def test_upgrade_old_firmware_manual_guidance_and_demo(self):
        page = FirmwareUpdatePage()
        page.validated_path = "test.uf2"
        page.set_context(True, True, {})
        self.assertFalse(page.upgrade_button.isEnabled())
        self.assertTrue(page.manual_button.isEnabled())
        self.assertIn("BOOT", page.guidance.text())
        page.set_context(False, False, {})
        self.assertTrue(page.manual_button.isEnabled())
        demo = FirmwareUpdatePage(demo=True); demo.validated_path="test.uf2"
        demo.set_context(True,True,{"bootsel":1})
        writes=[]; demo.upgrade_requested.connect(lambda *args:writes.append(args))
        demo.start_upgrade(); demo.start_manual()
        self.assertEqual(writes, [])

    def test_upgrade_progress_and_failure_recovery(self):
        page = FirmwareUpdatePage(); page.validated_path="test.uf2"
        page.set_context(True,True,{"bootsel":1})
        page.update_upgrade(dict(stage="copying",progress=45,busy=True,error="",detail="UF2"))
        self.assertFalse(page.upgrade_button.isEnabled())
        self.assertEqual(page.progress.value(),45)
        self.assertIn("写入",page.stage_label.text())
        page.update_upgrade(dict(stage="failed",progress=45,busy=False,error="磁盘已断开",detail=""))
        self.assertIn("磁盘已断开",page.status_label.text())
        self.assertIn("BOOT",page.status_label.text())
        self.assertTrue(page.upgrade_button.isEnabled())

    def test_validated_file_summary_and_invalid_reselection_block_upgrade(self):
        page=FirmwareUpdatePage();page.set_context(True,True,{"bootsel":1})
        requests=[];page.upgrade_requested.connect(lambda *args:requests.append(args))
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"bridge.uf2";file.write_bytes(convert(bytes(512)))
            self.assertTrue(page.select_file(file))
            self.assertIn("2 个 UF2 块",page.image_info.text())
            self.assertIn("10000000",page.image_info.text())
            self.assertIn("SHA-256",page.image_info.text())
            page.start_upgrade();self.assertEqual(requests,[(str(file),False)])
            file.write_bytes(b"bad file")
            self.assertFalse(page.select_file(file))
            self.assertFalse(page.upgrade_button.isEnabled())
            self.assertFalse(page.manual_button.isEnabled())
            page.start_upgrade();self.assertEqual(len(requests),1)


if __name__ == "__main__": unittest.main()
