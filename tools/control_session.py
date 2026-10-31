"""Qt-facing serial session. The worker owns every serial operation.

Polling has no job queue: a slow request moves the next deadline forward. A
single snapshot mailbox also bounds delivery when the GUI event loop is busy.
"""
from collections import deque
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

try:
    from .pedalctl import Client, CommandRejected, ProtocolError, open_link
except ImportError:
    from pedalctl import Client, CommandRejected, ProtocolError, open_link


def discover_ports():
    from serial.tools import list_ports
    return list_ports.comports()


class _Cancelled(Exception):
    pass


class Session(QObject):
    ports_changed = Signal(list)
    snapshot = Signal(dict)
    connected_changed = Signal(bool, str)
    message = Signal(str, bool)

    def __init__(self, parent=None, *, link_opener=None, port_provider=None,
                 client_factory=None, poll_interval=0.05, discovery_interval=0.5):
        super().__init__(parent)
        self._open = link_opener or open_link
        self._discover = port_provider or discover_ports
        self._client_factory = client_factory or Client
        self._poll_interval = max(0.05, poll_interval)
        self._discovery_interval = max(0.025, discovery_interval)
        self._condition = threading.Condition()
        self._epoch = 0
        self._stop = False
        self._desired = None
        self._suppressed = False
        self._connected = False
        self._target_serial = None
        self._jobs = deque()
        self._events = deque(maxlen=64)
        self._latest = None
        self._ports_event = None
        self._thread = None
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._drain)

    @Slot()
    def start(self):
        if self._thread is not None or self._stop:
            return
        self._thread = threading.Thread(target=self._run,
                                        name="control-center-serial", daemon=True)
        self._timer.start()
        self._thread.start()

    @Slot(str)
    def connect_port(self, device):
        device = str(device).strip()
        if not device:
            self.message.emit("请选择已识别的设备串口", True)
            return
        with self._condition:
            if self._stop:
                return
            self._epoch += 1
            self._desired = device
            self._connected = False
            self._suppressed = True  # an invalid explicit selection cannot open another board
            self._target_serial = None
            self._jobs.clear()
            self._latest = None
            self._condition.notify_all()

    @Slot()
    def disconnect_port(self):
        with self._condition:
            if self._stop:
                return
            self._epoch += 1
            self._desired = None
            self._connected = False
            self._suppressed = True
            self._jobs.clear()
            self._latest = None
            self._events.append((self._epoch, "connected", (False, "已断开")))
            self._condition.notify_all()

    @Slot(list)
    def submit(self, commands):
        if not isinstance(commands, list) or not commands or len(commands) > 64:
            self.message.emit("命令批次必须包含 1..64 条命令", True)
            return
        if any(not isinstance(c, str) or not c or len(c) > 127 or
               any(ord(ch) < 32 or ord(ch) > 126 for ch in c) for c in commands):
            self.message.emit("命令必须是最多 127 字符的单行 ASCII", True)
            return
        with self._condition:
            if self._stop or not self._connected:
                problem = "设备未连接；命令未排队"
            elif len(self._jobs) >= 8:
                problem = "设备操作队列已满，请等待当前操作完成"
            else:
                self._jobs.append((self._epoch, tuple(commands)))
                self._condition.notify_all()
                return
        self.message.emit(problem, True)

    @Slot()
    def close(self):
        self._timer.stop()
        with self._condition:
            if not self._stop:
                self._stop = True
                self._epoch += 1
                self._connected = False
                self._jobs.clear()
                self._latest = None
                self._events.clear()
                self._condition.notify_all()
        # pedalctl bounds each in-flight request at four seconds. The worker
        # checks cancellation between requests and closes its own link.
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=6)

    def _check(self, epoch):
        with self._condition:
            if self._stop or epoch != self._epoch:
                raise _Cancelled()

    def _event(self, epoch, kind, *payload):
        with self._condition:
            if not self._stop and epoch == self._epoch:
                self._events.append((epoch, kind, payload))

    def _publish(self, epoch, state):
        with self._condition:
            if self._stop or epoch != self._epoch:
                return
            if self._latest is not None:
                previous = self._latest[1]
                # Polls must preserve an undelivered SAVE acknowledgement,
                # but a later modifying batch supersedes that saved state.
                if not state["refresh_config"]:
                    state["saved"] |= previous["saved"]
                state["refresh_config"] |= previous["refresh_config"]
            self._latest = (epoch, state)

    @Slot()
    def _drain(self):
        with self._condition:
            epoch = self._epoch
            events, self._events = self._events, deque(maxlen=64)
            latest, self._latest = self._latest, None
            ports, self._ports_event = self._ports_event, None
            stopped = self._stop
        if stopped:
            return
        if ports is not None:
            self.ports_changed.emit(ports)
        for event_epoch, kind, payload in events:
            if event_epoch == self._epoch and not self._stop:
                if kind == "connected":
                    self.connected_changed.emit(*payload)
                else:
                    self.message.emit(*payload)
        if latest is not None and latest[0] == self._epoch and not self._stop:
            self.snapshot.emit(latest[1])

    def _scan(self):
        records = []
        for info in self._discover():
            if info.vid == 0xCAFE and info.pid in (0x4011, 0x4012):
                records.append({"device": info.device,
                                "description": info.description or "RP2350",
                                "serial_number": info.serial_number or None})
        return sorted(records, key=lambda p: p["device"])

    def _read(self, client, epoch, caps, profile, refresh, saved=False):
        self._check(epoch)
        pedal = client.get()
        self._check(epoch)
        if refresh and caps.get("profile"):
            try:
                profile = client.request("PROFILE")
                if not isinstance(profile, dict):
                    raise ProtocolError("Invalid PROFILE reply")
            except CommandRejected as exc:
                caps.pop("profile", None)
                profile = None
                self._event(epoch, "message", "固件不支持 PROFILE：" + str(exc), True)
        self._check(epoch)
        telemetry = None
        if caps.get("telemetry"):
            try:
                telemetry = client.request("TELEMETRY")
                if not isinstance(telemetry, dict):
                    raise ProtocolError("Invalid TELEMETRY reply")
            except CommandRejected as exc:
                caps.pop("telemetry", None)
                self._event(epoch, "message", "固件不支持 TELEMETRY：" + str(exc), True)
        self._check(epoch)
        return {"pedal": pedal, "telemetry": telemetry, "profile": profile,
                "capabilities": dict(caps), "refresh_config": refresh, "saved": saved}

    def _failed(self, epoch, error):
        with self._condition:
            if self._stop or epoch != self._epoch:
                return
            self._epoch += 1
            self._connected = False
            self._desired = None
            self._jobs.clear()
            self._latest = None
            self._suppressed = not bool(self._target_serial)
            self._events.append((self._epoch, "connected", (False, "连接已关闭")))
            self._events.append((self._epoch, "message", ("串口连接失败：" + str(error), True)))

    def _run(self):
        link = client = None
        local_epoch = -1
        caps, profile, records = {}, None, []
        next_scan = next_poll = 0.0
        previous_ports = None
        try:
            while True:
                with self._condition:
                    if self._stop:
                        return
                    epoch = self._epoch
                    desired = self._desired
                if local_epoch != epoch:
                    if link is not None:
                        link.close()
                    link = client = None
                    caps, profile = {}, None
                    local_epoch = epoch
                now = time.monotonic()
                if now >= next_scan or desired is not None:
                    try:
                        records = self._scan()
                    except Exception as exc:
                        records = []
                        self._event(epoch, "message", "串口扫描失败：" + str(exc), True)
                    if records != previous_ports:
                        previous_ports = records
                        with self._condition:
                            self._ports_event = records
                    next_scan = time.monotonic() + self._discovery_interval
                if link is None:
                    candidate = None
                    with self._condition:
                        if epoch != self._epoch:
                            continue
                        if desired is not None:
                            self._desired = None
                            candidate = next((p for p in records if p["device"] == desired), None)
                            if candidate is None:
                                self._events.append((epoch, "connected", (False, "未识别的串口")))
                                self._events.append((epoch, "message", ("拒绝打开未识别的串口：" + desired, True)))
                        elif not self._suppressed:
                            matching = ([p for p in records if p["serial_number"] == self._target_serial]
                                        if self._target_serial else records)
                            if len(matching) == 1:
                                candidate = matching[0]
                    if candidate is not None:
                        try:
                            self._check(epoch)
                            link = self._open(candidate["device"])
                            self._check(epoch)
                            client = self._client_factory(link)
                            try:
                                caps = client.request("CAPS")
                                if not isinstance(caps, dict):
                                    raise ProtocolError("Invalid CAPS reply")
                            except CommandRejected:
                                caps = {}
                            state = self._read(client, epoch, caps, None, True)
                            profile = state["profile"]
                            with self._condition:
                                self._check(epoch)
                                self._connected = True
                                self._target_serial = candidate["serial_number"]
                                self._suppressed = False
                            self._event(epoch, "connected", True, candidate["device"])
                            self._publish(epoch, state)
                            next_poll = time.monotonic() + self._poll_interval
                        except _Cancelled:
                            continue
                        except Exception as exc:
                            self._failed(epoch, exc)
                            continue
                if link is not None:
                    try:
                        self._check(epoch)
                        with self._condition:
                            batch = self._jobs.popleft() if self._jobs else None
                        if batch is not None:
                            batch_epoch, commands = batch
                            self._check(batch_epoch)
                            saved = False
                            rejected = False
                            for command in commands:
                                self._check(epoch)
                                try:
                                    client.request(command)
                                    saved |= command == "SAVE"
                                except CommandRejected as exc:
                                    rejected = True
                                    self._event(epoch, "message", "设备拒绝 " + command + "：" + str(exc) + "；连接保持", True)
                                    break
                            state = self._read(client, epoch, caps, profile, True, saved)
                            profile = state["profile"]
                            self._publish(epoch, state)
                            if not rejected:
                                self._event(epoch, "message", "已保存到 Flash" if saved else "操作完成；参数仅在 RAM 中", False)
                            next_poll = time.monotonic() + self._poll_interval
                        elif time.monotonic() >= next_poll:
                            state = self._read(client, epoch, caps, profile, False)
                            self._publish(epoch, state)
                            next_poll = time.monotonic() + self._poll_interval
                    except _Cancelled:
                        continue
                    except Exception as exc:
                        self._failed(epoch, exc)
                        continue
                with self._condition:
                    if self._stop or epoch != self._epoch or self._jobs or self._desired is not None:
                        continue
                    deadline = min(next_scan, next_poll) if link is not None else next_scan
                    self._condition.wait(timeout=max(0, deadline - time.monotonic()))
        finally:
            if link is not None:
                link.close()
