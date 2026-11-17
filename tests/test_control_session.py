"""Qt session tests use simulated serial endpoints, never attached hardware."""
import os
import threading
import time
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from tools import control_session
from tools.pedalctl import CommandRejected
from tools.bin_to_uf2 import convert
from tools.firmware_update import FirmwareUpdater, BootDrive


def port(device="COM_A", serial="board-a", vid=0xCAFE, pid=0x4012):
    return SimpleNamespace(device=device, serial_number=serial, vid=vid, pid=pid,
                           description="RP2350 Control Center")


class Link:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Endpoint:
    def __init__(self, legacy=False):
        self.legacy = legacy
        self.calls = []
        self.links = []
        self.fail = {}
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = None
        self.extra_caps = {}

    def open(self, name):
        link = Link()
        self.links.append((name, link, threading.get_ident()))
        return link

    def client(self, link):
        return self

    def get(self):
        return self.request("GET")

    def request(self, command):
        self.calls.append((command, time.monotonic(), threading.get_ident()))
        if command == self.block:
            self.entered.set()
            self.release.wait(2)
        if command in self.fail:
            raise self.fail[command]
        if command == "CAPS":
            if self.legacy:
                raise CommandRejected("ERR UNKNOWN_COMMAND")
            return {"profile": 1, "telemetry": 1, "control_center": 1, "bridge": 1, **self.extra_caps}
        if command == "BOOTSEL":
            return {"bootsel": True}
        if command in ("USBMODE WHEEL", "USBMODE XINPUT"):
            return {"usb_switch": True}
        if command == "RUMBLE":
            return {"testing": False, "remaining_ms": 0}
        if command == "GET":
            return {"protocol": 1, "raw": [10, 20], "output": [0, 0]}
        if command == "PROFILE":
            return {"sticks": [], "triggers": [], "bindings": []}
        if command == "TELEMETRY":
            return {"raw": [0] * 7, "processed": [0] * 7,
                    "output": [0] * 7, "state": 3, "keys": [0] * 8}
        return None


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.endpoint = Endpoint()
        self.ports = [port()]
        self.sessions = []

    def tearDown(self):
        self.endpoint.release.set()
        for session in self.sessions:
            session.close()
        self.app.processEvents()

    def make(self, start=True, **kwargs):
        session = control_session.Session(
            link_opener=self.endpoint.open, port_provider=lambda: list(self.ports),
            client_factory=self.endpoint.client, discovery_interval=0.025, **kwargs)
        self.sessions.append(session)
        self.snapshots, self.connections, self.messages, self.port_events = [], [], [], []
        session.snapshot.connect(self.snapshots.append)
        session.connected_changed.connect(lambda *args: self.connections.append(args))
        session.message.connect(lambda *args: self.messages.append(args))
        session.ports_changed.connect(self.port_events.append)
        if start:
            session.start()
        return session

    def until(self, predicate, timeout=2):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Session condition timed out")

    def connected(self):
        session = self.make()
        self.until(lambda: self.connections and self.connections[-1][0])
        return session

    def test_auto_discovery_opens_only_unique_known_identity(self):
        self.ports = [port("OTHER", vid=0x1234), port()]
        self.connected()
        self.assertEqual([x[0] for x in self.endpoint.links], ["COM_A"])
        self.assertEqual(self.port_events[-1], [{"device": "COM_A",
            "description": "RP2350 Control Center", "serial_number": "board-a", "pid": 0x4012}])
        self.assertNotEqual(self.endpoint.links[0][2], threading.get_ident())

    def test_multiple_candidates_require_selection_and_unknown_port_is_rejected(self):
        self.ports.append(port("COM_B", "board-b", pid=0x4011))
        session = self.make()
        self.until(lambda: bool(self.port_events))
        self.assertEqual(self.endpoint.links, [])
        session.connect_port("UNIDENTIFIED")
        self.until(lambda: bool(self.messages))
        self.assertEqual(self.endpoint.links, [])
        session.connect_port("COM_B")
        self.until(lambda: self.connections and self.connections[-1][0])
        self.assertEqual(self.endpoint.links[0][0], "COM_B")

    def test_capabilities_and_profile_refresh_only_on_connect_and_batch(self):
        session = self.connected()
        self.assertTrue(self.snapshots[0]["refresh_config"])
        self.assertIsNotNone(self.snapshots[0]["telemetry"])
        self.until(lambda: len(self.snapshots) >= 3)
        self.assertFalse(self.snapshots[-1]["refresh_config"])
        self.assertEqual(sum(c[0] == "PROFILE" for c in self.endpoint.calls), 1)
        session.submit(["STICK 0 0 100 0", "TRIGGER 0 0 100"])
        self.until(lambda: sum(c[0] == "PROFILE" for c in self.endpoint.calls) == 2)
        self.until(lambda: any(x["refresh_config"] for x in self.snapshots[1:]))
        self.assertNotIn("SAVE", [c[0] for c in self.endpoint.calls])

    def test_legacy_caps_rejection_produces_no_invented_telemetry(self):
        self.endpoint.legacy = True
        self.connected()
        state = self.snapshots[0]
        self.assertEqual(state["capabilities"], {})
        self.assertIsNone(state["telemetry"])
        self.assertIsNone(state["profile"])
        self.assertNotIn("TELEMETRY", [c[0] for c in self.endpoint.calls])

    def test_polling_is_bounded_and_does_not_queue_snapshots(self):
        self.connected()
        self.until(lambda: sum(c[0] == "GET" for c in self.endpoint.calls) >= 4)
        times = [c[1] for c in self.endpoint.calls if c[0] == "GET"]
        self.assertTrue(all(b - a >= 0.045 for a, b in zip(times, times[1:])))
        self.snapshots.clear()
        time.sleep(0.22)  # UI is busy: only the most recent snapshot may survive.
        self.app.processEvents()
        self.assertLessEqual(len(self.snapshots), 1)

    def test_rejected_batch_keeps_connection_and_refreshes_actual_config(self):
        session = self.connected()
        self.endpoint.fail["BIND 0 1 4"] = CommandRejected("ERR STATE_OR_VALUE")
        session.submit(["BIND 0 1 4", "BIND 1 1 5"])
        self.until(lambda: any(error for text, error in self.messages))
        self.until(lambda: sum(c[0] == "PROFILE" for c in self.endpoint.calls) == 2)
        self.assertNotIn("BIND 1 1 5", [c[0] for c in self.endpoint.calls])
        self.assertTrue(self.connections[-1][0])
        self.assertFalse(self.endpoint.links[0][1].closed)

    def test_save_acknowledgement_is_explicit_and_survives_busy_ui(self):
        session = self.connected()
        session.submit(["SAVE"])
        time.sleep(0.16)
        self.app.processEvents()
        self.assertTrue(self.snapshots[-1]["saved"])
        self.assertTrue(self.snapshots[-1]["refresh_config"])
        self.until(lambda: not self.snapshots[-1]["saved"])

    def test_disconnect_drops_pending_commands_and_stale_inflight_snapshot(self):
        session = self.connected()
        self.endpoint.block = "STICK 0 0 100 0"
        session.submit(["STICK 0 0 100 0", "BIND 0 1 4"])
        self.until(self.endpoint.entered.is_set)
        session.submit(["SAVE"])
        session.disconnect_port()
        self.endpoint.release.set()
        self.until(lambda: self.endpoint.links[0][1].closed)
        self.until(lambda: self.connections and not self.connections[-1][0])
        count = len(self.snapshots)
        time.sleep(0.08)
        self.app.processEvents()
        self.assertEqual(len(self.snapshots), count)
        self.assertNotIn("SAVE", [c[0] for c in self.endpoint.calls])
        self.assertNotIn("BIND 0 1 4", [c[0] for c in self.endpoint.calls])
        self.assertEqual(len(self.endpoint.links), 1)

    def test_transport_failure_reconnects_same_serial_only(self):
        self.connected()
        self.endpoint.fail["GET"] = OSError("unplugged")
        self.ports = [port("COM_B", "board-b")]
        self.until(lambda: self.endpoint.links[0][1].closed)
        time.sleep(0.1)
        self.app.processEvents()
        self.assertEqual(len(self.endpoint.links), 1)
        self.endpoint.fail.clear()
        self.ports.append(port("COM_NEW", "board-a"))
        self.until(lambda: len(self.endpoint.links) == 2)
        self.assertEqual(self.endpoint.links[-1][0], "COM_NEW")

    def test_usb_mode_switch_waits_for_new_pid_on_same_board(self):
        session = self.connected()
        session.submit(["USBMODE WHEEL"])
        self.until(lambda: self.endpoint.links[0][1].closed)
        self.ports.append(port("COM_OTHER", "board-b", pid=0x4013))
        self.until(lambda: len(self.port_events[-1]) == 2)
        self.assertEqual(len(self.endpoint.links), 1)
        self.ports.append(port("COM_WHEEL", "board-a", pid=0x4013))
        self.until(lambda: self.connections[-1] == (True, "COM_WHEEL"))
        self.assertEqual([link[0] for link in self.endpoint.links], ["COM_A", "COM_WHEEL"])
        self.assertEqual([c[0] for c in self.endpoint.calls].count("USBMODE WHEEL"), 1)

    def test_validation_and_offline_submit_do_not_open_or_replay_commands(self):
        self.ports = []
        session = self.make()
        session.submit(["SAVE"])
        self.until(lambda: bool(self.messages))
        self.ports = [port()]
        self.until(lambda: bool(self.snapshots))
        session.submit(["SAVE\nGET"])
        self.until(lambda: len(self.messages) >= 2)
        self.assertNotIn("SAVE", [c[0] for c in self.endpoint.calls])

    def test_close_is_idempotent_and_closes_link_on_worker(self):
        session = self.connected()
        session.close()
        session.close()
        self.assertTrue(self.endpoint.links[0][1].closed)
        self.assertFalse(session._thread.is_alive())

    def test_signal_callback_disconnect_cannot_deliver_stale_snapshot(self):
        session = self.make(start=False)
        session.connected_changed.connect(
            lambda connected, detail: session.disconnect_port() if connected else None)
        session.start()
        self.until(lambda: self.connections and not self.connections[-1][0])
        self.assertEqual(self.snapshots, [])

    def test_later_apply_cancels_pending_save_indication(self):
        session = self.connected()
        session.submit(["SAVE"])
        end = time.monotonic() + 1
        while not any(c[0] == "SAVE" for c in self.endpoint.calls) and time.monotonic() < end:
            time.sleep(0.005)
        session.submit(["STICK 0 10 100 0"])
        time.sleep(0.12)
        self.app.processEvents()
        self.assertFalse(self.snapshots[-1]["saved"])

    def test_advertised_unsupported_telemetry_is_disabled_without_losing_link(self):
        self.endpoint.fail["TELEMETRY"] = CommandRejected("ERR UNKNOWN_COMMAND")
        self.connected()
        self.until(lambda: len(self.snapshots) >= 2)
        self.assertIsNone(self.snapshots[-1]["telemetry"])
        self.assertNotIn("telemetry", self.snapshots[-1]["capabilities"])
        self.assertEqual(sum(c[0] == "TELEMETRY" for c in self.endpoint.calls), 1)
        self.assertFalse(self.endpoint.links[0][1].closed)

    def test_close_cancels_remaining_batch_after_inflight_request_returns(self):
        session = self.connected()
        self.endpoint.block = "SAVE"
        session.submit(["SAVE", "BIND 0 1 4"])
        self.until(self.endpoint.entered.is_set)
        release = threading.Timer(0.05, self.endpoint.release.set)
        release.start()
        begin = time.monotonic()
        session.close()
        release.join()
        self.assertLess(time.monotonic() - begin, 0.5)
        self.assertNotIn("BIND 0 1 4", [c[0] for c in self.endpoint.calls])
        self.assertTrue(self.endpoint.links[0][1].closed)

    def updater_session(self, *, writer=None, drives=None, timeout=0.1):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.image_path = str(Path(directory.name) / 'firmware.uf2')
        Path(self.image_path).write_bytes(convert(bytes(512)))
        self.drives = []
        self.writes, self.upgrades = [], []
        def default_writer(drive, data, progress):
            self.assertTrue(self.endpoint.links[-1][1].closed)
            self.writes.append((drive, data))
            self.ports = [port('COM_OTHER', 'board-b'), port('COM_NEW', 'board-a')]
            progress(100)
        updater = FirmwareUpdater(drive_provider=drives or (lambda: list(self.drives)),
                                  writer=writer or default_writer, timeout=timeout, poll_interval=0.005)
        session = self.make(updater=updater, reconnect_timeout=0.15)
        session.upgrade_changed.connect(self.upgrades.append)
        self.until(lambda: self.connections and self.connections[-1][0])
        return session

    def test_rumble_diagnostic_is_polled_only_when_advertised(self):
        self.endpoint.extra_caps['rumble'] = 1
        self.connected()
        self.assertEqual(self.snapshots[-1]['rumble']['remaining_ms'], 0)
        self.assertIn('RUMBLE', [x[0] for x in self.endpoint.calls])

    def test_upgrade_reconnects_same_serial_after_state_reread_and_no_replay(self):
        self.endpoint.extra_caps['bootsel'] = 1
        self.endpoint.extra_caps['version'] = '0.5.0'
        scans = iter([[], [BootDrive('A:/', 'rom')], [BootDrive('A:/', 'rom')]])
        session = self.updater_session(drives=lambda: next(scans))
        session.upgrade(self.image_path)
        session.submit(['SAVE'])
        self.until(lambda: any(x['stage'] == 'complete' for x in self.upgrades))
        self.assertEqual(len(self.writes), 1)
        self.assertEqual([x[0] for x in self.endpoint.links], ['COM_A', 'COM_NEW'])
        self.assertEqual(sum(x[0] == 'BOOTSEL' for x in self.endpoint.calls), 1)
        self.assertNotIn('SAVE', [x[0] for x in self.endpoint.calls])
        self.assertGreaterEqual(sum(x[0] == 'GET' for x in self.endpoint.calls), 2)
        self.assertTrue(self.snapshots[-1]['refresh_config'])
        self.assertFalse(self.upgrades[-1]['busy'])
        self.assertIn('0.5.0', self.upgrades[-1]['detail'])

    def test_legacy_automatic_upgrade_explains_manual_and_does_not_reboot(self):
        session = self.updater_session()
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertIn('手动', self.upgrades[-1]['error'])
        self.assertNotIn('BOOTSEL', [x[0] for x in self.endpoint.calls])
        self.assertFalse(self.endpoint.links[0][1].closed)
        self.assertTrue(session._connected)

    def test_bootsel_rejection_preserves_connection_without_writing(self):
        self.endpoint.extra_caps['bootsel'] = 1
        self.endpoint.fail['BOOTSEL'] = CommandRejected('ERR STATE')
        session = self.updater_session()
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertEqual(self.writes, [])
        self.assertTrue(session._connected)

    def test_missing_drive_fails_once_and_does_not_flash_preexisting_drive(self):
        self.endpoint.extra_caps['bootsel'] = 1
        session = self.updater_session(drives=lambda: [BootDrive('A:/', 'preexisting')])
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertEqual(self.writes, [])
        self.assertEqual(sum(x[0] == 'BOOTSEL' for x in self.endpoint.calls), 1)

    def test_explicit_manual_upgrade_writes_unique_existing_drive(self):
        session = self.updater_session(drives=lambda: [BootDrive('A:/', 'existing')])
        session.upgrade(self.image_path, manual=True)
        self.until(lambda: any(x['stage'] == 'complete' for x in self.upgrades))
        self.assertEqual(len(self.writes), 1)
        self.assertNotIn('BOOTSEL', [x[0] for x in self.endpoint.calls])

    def test_copy_close_is_refused_and_reconnect_failure_is_not_success(self):
        self.endpoint.extra_caps['bootsel'] = 1
        entered, release = threading.Event(), threading.Event()
        def writer(drive, data, progress):
            entered.set()
            release.wait(1)
            self.ports = [port('COM_OTHER', 'board-b')]
        self.addCleanup(release.set)
        scans = iter([[], [BootDrive('A:/', 'rom')], [BootDrive('A:/', 'rom')]])
        session = self.updater_session(writer=writer, drives=lambda: next(scans))
        session.upgrade(self.image_path)
        self.until(entered.is_set)
        self.assertFalse(session.close())
        self.assertFalse(session.cancel_upgrade())
        session.connect_port('COM_OTHER')
        session.disconnect_port()
        release.set()
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertFalse(any(x['stage'] == 'complete' for x in self.upgrades))
        self.assertEqual(len(self.endpoint.links), 1)

    def test_cancel_while_waiting_drive_does_not_copy(self):
        self.endpoint.extra_caps['bootsel'] = 1
        session = self.updater_session(timeout=1)
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'waiting_drive' for x in self.upgrades))
        self.assertTrue(session.cancel_upgrade())
        self.until(lambda: any(x['stage'] == 'cancelled' for x in self.upgrades))
        self.assertEqual(self.writes, [])

    def test_cancel_during_reconnect_read_closes_new_link_and_never_completes(self):
        self.endpoint.extra_caps['bootsel'] = 1
        def writer(drive, data, progress):
            self.endpoint.block = 'GET'
            self.ports = [port('COM_NEW', 'board-a')]
        scans = iter([[], [BootDrive('A:/', 'rom')], [BootDrive('A:/', 'rom')]])
        session = self.updater_session(writer=writer, drives=lambda: next(scans))
        session.upgrade(self.image_path)
        self.until(self.endpoint.entered.is_set)
        self.assertTrue(session.cancel_upgrade())
        self.endpoint.release.set()
        self.until(lambda: any(x['stage'] == 'cancelled' for x in self.upgrades))
        self.assertFalse(any(x['stage'] == 'complete' for x in self.upgrades))
        self.assertTrue(self.endpoint.links[1][1].closed)

    def test_close_before_copy_cancels_worker_without_writing(self):
        self.endpoint.extra_caps['bootsel'] = 1
        session = self.updater_session(timeout=1)
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'waiting_drive' for x in self.upgrades))
        self.assertTrue(session.close())
        self.assertFalse(session._thread.is_alive())
        self.assertEqual(self.writes, [])

    def test_bad_image_fails_before_bootsel_and_preserves_live_session(self):
        self.endpoint.extra_caps['bootsel'] = 1
        session = self.updater_session()
        Path(self.image_path).write_bytes(b'bad uf2')
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertNotIn('BOOTSEL', [x[0] for x in self.endpoint.calls])
        self.assertTrue(session._connected)
        self.assertFalse(self.endpoint.links[0][1].closed)

    def test_manual_without_previously_captured_serial_does_not_write(self):
        self.ports = []
        # Construct offline without helper's connected wait.
        updater = FirmwareUpdater(drive_provider=lambda: [BootDrive('A:/', 'rom')],
                                  writer=lambda *args: self.fail('unbound board written'))
        session = self.make(updater=updater)
        upgrades = []
        session.upgrade_changed.connect(upgrades.append)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'firmware.uf2'
            path.write_bytes(convert(bytes(256)))
            session.upgrade(str(path), manual=True)
            self.until(lambda: any(x['stage'] == 'failed' for x in upgrades))
        self.assertIn('序列号', upgrades[-1]['error'])

    def test_writer_failure_is_not_retried_and_session_releases_upgrade_gate(self):
        self.endpoint.extra_caps['bootsel'] = 1
        attempts = []
        def writer(*args):
            attempts.append(1)
            raise OSError('disk vanished')
        scans = iter([[], [BootDrive('A:/', 'rom')], [BootDrive('A:/', 'rom')]])
        session = self.updater_session(writer=writer, drives=lambda: next(scans))
        session.upgrade(self.image_path)
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertEqual(len(attempts), 1)
        self.assertFalse(session._upgrade_busy)
        self.assertIn('disk vanished', self.upgrades[-1]['error'])

    def test_failed_upgrade_status_survives_later_transport_epoch_with_busy_ui(self):
        self.endpoint.extra_caps['bootsel'] = 1
        session = self.updater_session()
        self.endpoint.fail['BOOTSEL'] = TimeoutError('ACK lost')
        self.endpoint.fail['GET'] = OSError('device now in BOOTSEL')
        self.ports = []
        session.upgrade(self.image_path)
        time.sleep(0.2)  # Qt is busy while the worker advances transport epoch.
        self.app.processEvents()
        self.assertTrue(any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertFalse(self.upgrades[-1]['busy'])
        self.assertIn('ACK lost', self.upgrades[-1]['error'])
        self.assertFalse(session._upgrade_busy)

    def test_complete_upgrade_status_survives_immediate_unplug_with_busy_ui(self):
        self.endpoint.extra_caps['bootsel'] = 1
        scans = iter([[], [BootDrive('A:/', 'rom')], [BootDrive('A:/', 'rom')]])
        session = self.updater_session(drives=lambda: next(scans))
        original_get = self.endpoint.get
        reads = []
        def get_then_unplug():
            value = original_get()
            reads.append(1)
            self.endpoint.fail['GET'] = OSError('unplugged after restored state')
            self.ports = []
            return value
        self.endpoint.get = get_then_unplug
        session.upgrade(self.image_path)
        time.sleep(0.2)
        self.app.processEvents()
        self.assertEqual(len(reads), 1)
        self.assertTrue(any(x['stage'] == 'complete' for x in self.upgrades))
        self.assertFalse(self.upgrades[-1]['busy'])

    def test_stop_preempts_full_test_queue_preserves_config_and_does_not_replay(self):
        session = self.connected()
        test = 'RUMBLE TEST 64 64 3000'
        self.endpoint.block = test
        session.submit([test, test, 'BIND 0 1 4'])
        self.until(self.endpoint.entered.is_set)
        for _ in range(7):
            session.submit([test])
        session.submit([test, 'SAVE'])
        session.submit(['RUMBLE STOP'])
        session.submit(['RUMBLE STOP'])
        self.endpoint.release.set()
        self.until(lambda: any(x[0] == 'SAVE' for x in self.endpoint.calls))
        calls = [x[0] for x in self.endpoint.calls]
        first_test = calls.index(test)
        self.assertEqual(calls[first_test + 1], 'RUMBLE STOP')
        self.assertEqual(calls.count('RUMBLE STOP'), 1)
        self.assertEqual(calls.count(test), 1)
        self.assertIn('BIND 0 1 4', calls)
        self.assertIn('SAVE', calls)
        session.disconnect_port()
        self.until(lambda: self.endpoint.links[0][1].closed)
        session.connect_port('COM_A')
        self.until(lambda: len(self.endpoint.links) == 2)
        self.assertEqual([x[0] for x in self.endpoint.calls].count('RUMBLE STOP'), 1)
        self.assertEqual([x[0] for x in self.endpoint.calls].count(test), 1)

    def test_terminal_upgrade_status_is_not_visible_until_retry_gate_released(self):
        session = self.updater_session()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = session._upgrade_event
        def delayed_finally(epoch, stage, *args, **kwargs):
            original(epoch, stage, *args, **kwargs)
            if stage == 'failed':
                entered.set()
                release.wait(1)
        session._upgrade_event = delayed_finally
        session.upgrade(self.image_path)
        self.until(entered.is_set)
        session._drain()
        self.assertFalse(any(x['stage'] == 'failed' for x in self.upgrades))
        release.set()
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertFalse(session._upgrade_busy)

    def test_upgrade_clears_queue_and_interrupts_remaining_batch(self):
        self.endpoint.extra_caps['bootsel'] = 1
        session = self.updater_session()
        self.endpoint.block = 'STICK 0 0 100 0'
        session.submit(['STICK 0 0 100 0', 'SAVE'])
        self.until(self.endpoint.entered.is_set)
        session.submit(['BIND 0 1 4'])
        session.upgrade(self.image_path)
        self.endpoint.release.set()
        self.until(lambda: any(x['stage'] == 'failed' for x in self.upgrades))
        self.assertNotIn('SAVE', [x[0] for x in self.endpoint.calls])
        self.assertNotIn('BIND 0 1 4', [x[0] for x in self.endpoint.calls])


if __name__ == "__main__":
    unittest.main()
