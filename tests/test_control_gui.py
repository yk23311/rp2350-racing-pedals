"""Qt control center behavior, without serial hardware."""
import copy
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from tools.control_center import ControlCenter
from tools.control_widgets import CurvePlot, PedalGauge, StickView


def snapshot():
    return {"refresh_config": True, "capabilities": {"profile": 1, "telemetry": 1},
            "pedal": {"mode": "JOYSTICK", "armed": True, "calibration_axis": -1,
                      "axes": [{"on": 300, "off": 100, "gamma": 100, "window": 4,
                                "released": 300, "pressed": 3600, "calibrated": True} for _ in range(2)],
                      "raw": [1000, 2000], "filtered": [900, 1900], "output": [46, 124]},
            "profile": {"sticks": [{"deadzone": 0, "gamma": 100, "invert": 0} for _ in range(2)],
                        "triggers": [{"deadzone": 0, "gamma": 100} for _ in range(2)],
                        "bindings": [[0, i] for i in range(14)]},
            "telemetry": {"state": 3, "age": 10, "reports": 100, "timeouts": 0,
                          "raw": [4096, 30, 80, 1000, -2000, 0, 0],
                          "processed": [4096, 30, 80, 1000, -2000, 0, 0],
                          "output": [4096, 46, 124, 1000, -2000, 0, 0]}}


class FakeSession(QObject):
    ports_changed = Signal(list)
    snapshot = Signal(dict)
    connected_changed = Signal(bool, str)
    message = Signal(str, bool)

    def __init__(self):
        super().__init__(); self.commands = []; self.closed = False
    def start(self): pass
    def submit(self, commands): self.commands.append(commands)
    def connect_port(self, port): pass
    def disconnect_port(self): pass
    def close(self): self.closed = True


class ControlGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.session = FakeSession()
        self.window = ControlCenter(self.session)
        self.session.connected_changed.emit(True, "COM8")
        self.session.snapshot.emit(snapshot())
    def tearDown(self): self.window.close()
    def test_polling_preserves_unsent_edits(self):
        self.window.pedal_editors[0]["gamma"].setValue(2.3)
        incoming = snapshot(); incoming["refresh_config"] = False
        self.session.snapshot.emit(incoming)
        self.assertEqual(self.window.pedal_editors[0]["gamma"].value(), 2.3)
        self.assertTrue(self.window.dirty)
    def test_apply_generates_board_commands_and_waits_for_ack(self):
        self.window.pedal_editors[0]["gamma"].setValue(2.3)
        self.window.stick_editors[1]["deadzone"].setValue(12.5)
        self.window.apply_changes()
        self.assertIn("SET 0 300 100 230 4", self.session.commands[-1])
        self.assertIn("STICK 1 1250 100 0", self.session.commands[-1])
        self.assertTrue(self.window.dirty)
        ack = snapshot(); ack["pedal"]["axes"][0]["gamma"] = 230
        ack["profile"]["sticks"][1]["deadzone"] = 1250
        self.session.snapshot.emit(ack)
        self.assertFalse(self.window.dirty)
        self.assertIn("未保存", self.window.persistence_label.text())
    def test_revert_restores_applied_values(self):
        self.window.pedal_editors[0]["gamma"].setValue(3)
        self.window.revert_changes()
        self.assertEqual(self.window.pedal_editors[0]["gamma"].value(), 1)
        self.assertFalse(self.window.dirty)
    def test_apply_ack_preserves_edits_made_while_waiting(self):
        self.window.pedal_editors[0]["gamma"].setValue(2)
        self.window.apply_changes()
        self.window.pedal_editors[0]["gamma"].setValue(3)
        ack = snapshot(); ack["pedal"]["axes"][0]["gamma"] = 200
        self.session.snapshot.emit(ack)
        self.assertEqual(self.window.pedal_editors[0]["gamma"].value(), 3)
        self.assertTrue(self.window.dirty)
        self.window.revert_changes()
        self.assertEqual(self.window.pedal_editors[0]["gamma"].value(), 2)
    def test_calibration_and_invalid_hysteresis(self):
        self.window._command("CAL 0 BEGIN")
        self.assertEqual(self.session.commands[-1], ["CAL 0 BEGIN"])
        self.window.pedal_editors[0]["off"].setValue(4)
        self.window.apply_changes()
        self.assertEqual(len(self.session.commands), 1)
        self.assertIn("释放阈值", self.window.notice_label.text())
    def test_small_window_keeps_footer_and_scrollable_controls(self):
        self.window.resize(900, 650); self.window.show(); self.app.processEvents()
        self.assertEqual(self.window.width(), 900)
        for index in range(self.window.tabs.count()):
            self.window.tabs.setCurrentIndex(index); self.app.processEvents()
            self.assertLess(self.window.save_button.mapTo(self.window, self.window.save_button.rect().bottomRight()).y(), self.window.height())
    def test_keyboard_modifier_binding_and_disable_commands(self):
        kind, target = self.window.binding_editors[0]
        kind.setCurrentIndex(kind.findData(1))
        target.setCurrentIndex(target.findData(0xE1))
        kind2, _ = self.window.binding_editors[1]
        kind2.setCurrentIndex(kind2.findData(2))
        self.window.apply_changes()
        self.assertIn("BIND 0 1 225", self.session.commands[-1])
        self.assertIn("BIND 1 2 0", self.session.commands[-1])
    def test_save_needs_board_ack(self):
        self.window.save_changes()
        self.assertEqual(self.session.commands[-1], ["SAVE"])
        self.assertNotIn("Flash 已保存", self.window.persistence_label.text())
        ack = snapshot(); ack["saved"] = True
        self.session.snapshot.emit(ack)
        self.assertIn("Flash 已保存", self.window.persistence_label.text())
    def test_calibration_after_save_marks_ram_unsaved_without_local_edits(self):
        ack = snapshot(); ack["saved"] = True
        self.session.snapshot.emit(ack)
        self.assertIn("Flash 已保存", self.window.persistence_label.text())
        calibrated = snapshot()
        calibrated["pedal"]["axes"][0]["pressed"] = 3700
        self.session.snapshot.emit(calibrated)
        self.assertIn("未保存", self.window.persistence_label.text())
        self.assertFalse(self.window.dirty)
        # Calibrated flags are persistent too, even with identical endpoints.
        calibrated["saved"] = True; self.session.snapshot.emit(calibrated)
        calibrated["saved"] = False
        calibrated["pedal"]["axes"][1]["calibrated"] = False
        self.session.snapshot.emit(calibrated)
        self.assertIn("未保存", self.window.persistence_label.text())
        self.assertFalse(self.window.dirty)
    def test_mapping_highlights_use_raw_sources_and_clear_when_not_fresh(self):
        incoming = snapshot()
        incoming["telemetry"]["raw"][0] = (1 << 0) | (1 << 15)
        incoming["telemetry"]["output"][0] = 1 << 12
        self.session.snapshot.emit(incoming)
        self.assertEqual(len(self.window.binding_source_labels), 14)
        self.assertTrue(self.window.binding_source_labels[0].property("pressed"))
        self.assertTrue(self.window.binding_source_labels[13].property("pressed"))
        self.assertFalse(self.window.binding_source_labels[10].property("pressed"))
        incoming["telemetry"]["age"] = 300
        self.session.snapshot.emit(incoming)
        self.assertFalse(any(w.property("pressed") for w in self.window.binding_source_labels))
        incoming["telemetry"]["age"] = 10
        self.session.snapshot.emit(incoming)
        self.session.connected_changed.emit(False, "已拔出")
        self.assertFalse(any(w.property("pressed") for w in self.window.binding_source_labels))
    def test_blocked_controller_is_visible_in_main_status(self):
        incoming = snapshot(); incoming["telemetry"]["blocked"] = True
        self.session.snapshot.emit(incoming)
        self.assertIn("等待手柄", self.window.device_state.text())
        self.assertIn("回零", self.window.device_detail.text())
    def test_reconnect_discards_draft_and_waits_for_new_device_config(self):
        self.window.pedal_editors[0]["gamma"].setValue(2.3)
        self.session.connected_changed.emit(False, "A 已拔出")
        self.session.connected_changed.emit(True, "B / COM9")
        self.assertFalse(self.window.dirty)
        self.assertFalse(self.window.apply_button.isEnabled())
        self.assertFalse(self.window.save_button.isEnabled())
        self.assertIn("已丢弃", self.window.notice_label.text())
        self.window.save_changes(); self.window.apply_changes()
        self.assertEqual(self.session.commands, [])
        incoming = snapshot()
        incoming["pedal"]["axes"][0]["gamma"] = 140
        incoming["pedal"]["axes"][1]["on"] = 700
        incoming["profile"]["sticks"][0]["gamma"] = 210
        self.session.snapshot.emit(incoming)
        self.assertFalse(self.window.dirty)
        self.assertEqual(self.window.pedal_editors[0]["gamma"].value(), 1.4)
        self.assertEqual(self.window.pedal_editors[1]["on"].value(), 7)
        self.assertEqual(self.window.stick_editors[0]["gamma"].value(), 2.1)
        self.assertFalse(self.window.apply_button.isEnabled())
        self.assertTrue(self.window.save_button.isEnabled())
    def test_output_shows_pedal_only_without_host_but_raw_stays_inactive(self):
        incoming = snapshot()
        incoming["telemetry"]["state"] = 0
        incoming["telemetry"]["age"] = 0xffffffff
        incoming["telemetry"]["raw"] = [0]*7
        incoming["telemetry"]["processed"] = [0]*7
        incoming["telemetry"]["output"] = [0, 0, 127, 0, 0, 0, 0]
        self.session.snapshot.emit(incoming)
        self.assertTrue(self.window.controller.active)
        self.assertEqual(self.window.live_triggers[1][1].value(), 127)
        self.assertIn("49.8%", self.window.live_triggers[1][0].text())
        self.assertIn("未接入", self.window.host_status.text())
        for source in ("raw", "processed"):
            self.window.source_combo.setCurrentIndex(self.window.source_combo.findData(source))
            self.assertFalse(self.window.controller.active)
            self.assertIn("—", self.window.live_triggers[1][0].text())
        self.session.connected_changed.emit(False, "已拔出")
        self.window.source_combo.setCurrentIndex(self.window.source_combo.findData("output"))
        self.assertFalse(self.window.controller.active)
    def test_mode_selector_explains_ram_only_lifetime(self):
        self.assertIn("RAM", self.window.mode_combo.toolTip())
        self.assertIn("JOYSTICK", self.window.mode_combo.toolTip())
    def test_connected_signal_alone_resets_previous_session(self):
        self.window.pedal_editors[0]["gamma"].setValue(2)
        self.session.connected_changed.emit(True, "新会话")
        self.assertFalse(self.window.dirty)
        self.assertIsNone(self.window._baseline)
        self.assertEqual(self.window._latest, {})
        self.assertFalse(self.window.save_button.isEnabled())
    def test_discovery_displays_serial_suffix_and_full_tooltip(self):
        self.session.ports_changed.emit([{"device":"COM9","description":"RP2350","serial_number":"RP2350ABC123456"}])
        self.assertIn("123456", self.window.port_combo.itemText(0))
        self.assertIn("RP2350ABC123456", self.window.port_combo.itemData(0, Qt.ToolTipRole))
    def test_unlabelled_legal_hid_binding_is_preserved_on_other_edits(self):
        incoming = snapshot(); incoming["profile"]["bindings"][0] = [1, 0xA5]
        self.session.snapshot.emit(incoming)
        kind, target = self.window.binding_editors[0]
        self.assertEqual(kind.currentData(), 1)
        self.assertEqual(target.currentData(), 0xA5)
        self.assertEqual(target.currentText(), "HID 0xA5")
        self.window.pedal_editors[0]["gamma"].setValue(1.7)
        self.window.apply_changes()
        self.assertEqual(self.session.commands[-1], ["SET 0 300 100 170 4"])
    def test_pc_snapshot_watchdog_greys_data_and_blocks_writes_then_recovers(self):
        with patch("tools.control_center.time.monotonic", return_value=100.0):
            self.session.snapshot.emit(snapshot())
        self.window.pedal_editors[0]["gamma"].setValue(1.8)
        with patch("tools.control_center.time.monotonic", return_value=100.6):
            self.window._watchdog_tick()
            self.assertFalse(self.window.gauges[0].active)
            self.assertFalse(self.window.controller.active)
            self.assertFalse(self.window.apply_button.isEnabled())
            self.assertFalse(self.window.save_button.isEnabled())
            self.assertTrue(all(not b.isEnabled() for b in self.window.calibration_buttons))
            self.assertIn("数据已过期，等待串口回复", self.window.edit_label.text())
            self.assertTrue(self.window.connected)
            self.assertTrue(self.window.dirty)
            self.window.apply_changes(); self.window.save_changes(); self.window._command("CAL 0 BEGIN")
            self.assertEqual(self.session.commands, [])
        with patch("tools.control_center.time.monotonic", return_value=100.61):
            incoming = snapshot(); incoming["refresh_config"] = False
            self.session.snapshot.emit(incoming)
            self.assertTrue(self.window.gauges[0].active)
            self.assertTrue(self.window.controller.active)
            self.assertTrue(self.window.apply_button.isEnabled())
            self.assertTrue(all(b.isEnabled() for b in self.window.calibration_buttons))
            self.assertEqual(self.window.pedal_editors[0]["gamma"].value(), 1.8)
            self.window.revert_changes()
            self.assertTrue(self.window.save_button.isEnabled())
    def test_host_age_includes_time_waiting_in_ui(self):
        with patch("tools.control_center.time.monotonic", return_value=100.0):
            incoming = snapshot(); incoming["telemetry"]["age"] = 100
            self.session.snapshot.emit(incoming)
            self.window.source_combo.setCurrentIndex(self.window.source_combo.findData("raw"))
            self.assertTrue(self.window.controller.active)
        with patch("tools.control_center.time.monotonic", return_value=100.2):
            self.window._watchdog_tick()
            self.assertTrue(self.window.gauges[0].active)
            self.assertFalse(self.window.controller.active)
            self.window.source_combo.setCurrentIndex(self.window.source_combo.findData("output"))
            self.assertTrue(self.window.controller.active)
    def test_stale_clean_config_cannot_save_until_next_snapshot(self):
        with patch("tools.control_center.time.monotonic", return_value=100.0):
            self.session.snapshot.emit(snapshot())
            self.assertTrue(self.window.save_button.isEnabled())
        with patch("tools.control_center.time.monotonic", return_value=100.6):
            self.window._watchdog_tick()
            self.assertFalse(self.window.save_button.isEnabled())
            self.window.save_changes()
            self.assertEqual(self.session.commands, [])
        with patch("tools.control_center.time.monotonic", return_value=100.7):
            self.session.snapshot.emit(snapshot())
            self.assertTrue(self.window.save_button.isEnabled())
    def test_legacy_and_disconnect_disable_board_actions(self):
        old = snapshot(); old["profile"] = None; old["telemetry"] = None; old["capabilities"] = {}
        self.session.snapshot.emit(old)
        self.assertFalse(self.window.stick_editors[0]["gamma"].isEnabled())
        self.assertTrue(self.window.pedal_editors[0]["gamma"].isEnabled())
        self.session.connected_changed.emit(False, "拔出")
        self.assertFalse(self.window.apply_button.isEnabled())
        self.assertFalse(self.window.save_button.isEnabled())
    def test_widgets_clamp_and_render_at_target_size(self):
        self.assertTrue(QFontDatabase.families(), "Offscreen screenshots need readable installed fonts")
        gauge = PedalGauge("油门", "#43ddbd"); gauge.set_value(200)
        self.assertEqual(gauge.value, 100)
        gauge.set_value(-10); self.assertEqual(gauge.value, 0)
        stick = StickView(); stick.set_value(50000, -50000)
        self.assertLessEqual(abs(stick.x), 1); self.assertLessEqual(abs(stick.y), 1)
        self.window.resize(1280, 800); self.window.show(); self.app.processEvents()
        self.assertFalse(self.window.grab().isNull())
        for index in range(self.window.tabs.count()):
            self.window.tabs.setCurrentIndex(index); self.app.processEvents()
            self.assertFalse(self.window.grab().isNull())
            if index in (1, 2):
                self.assertEqual(self.window.tabs.widget(index).verticalScrollBar().maximum(), 0,
                                 "Primary tuning controls must fit at 1280x800")


if __name__ == "__main__": unittest.main()
