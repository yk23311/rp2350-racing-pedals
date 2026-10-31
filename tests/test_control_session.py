"""Qt session tests use simulated serial endpoints, never attached hardware."""
import os
import threading
import time
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from tools import control_session
from tools.pedalctl import CommandRejected


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
            return {"profile": 1, "telemetry": 1, "control_center": 1, "bridge": 1}
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

    def make(self, start=True):
        session = control_session.Session(
            link_opener=self.endpoint.open, port_provider=lambda: list(self.ports),
            client_factory=self.endpoint.client, discovery_interval=0.025)
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
            "description": "RP2350 Control Center", "serial_number": "board-a"}])
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


if __name__ == "__main__":
    unittest.main()
