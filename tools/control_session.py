"""Qt-facing serial session. The worker owns every serial operation.

Polling has no job queue: a slow request moves the next deadline forward. A
single snapshot mailbox also bounds delivery when the GUI event loop is busy.
"""
from collections import deque
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

USB_MODE_PIDS = {"USBMODE XINPUT": 0x4012, "USBMODE WHEEL": 0x4013}

try:
    from .pedalctl import Client, CommandRejected, ProtocolError, open_link
    from .firmware_update import FirmwareUpdater, UpgradeCancelled
except ImportError:
    from pedalctl import Client, CommandRejected, ProtocolError, open_link
    from firmware_update import FirmwareUpdater, UpgradeCancelled


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
    upgrade_changed = Signal(dict)

    def __init__(self, parent=None, *, link_opener=None, port_provider=None,
                 client_factory=None, poll_interval=0.05, discovery_interval=0.5,
                 updater=None, reconnect_timeout=30):
        super().__init__(parent)
        self._open = link_opener or open_link
        self._discover = port_provider or discover_ports
        self._client_factory = client_factory or Client
        self._updater = updater or FirmwareUpdater()
        self._reconnect_timeout = reconnect_timeout
        self._upgrade_pending = None
        self._upgrade_busy = False
        self._upgrade_copying = False
        self._upgrade_cancel = False
        self._upgrade_generation = 0
        self._upgrade_events = deque(maxlen=64)
        self._upgrade_terminal = None
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
        self._priority_stop = False
        self._rumble_generation = 0
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
            if self._stop or self._upgrade_busy:
                return
            self._epoch += 1
            self._desired = device
            self._connected = False
            self._suppressed = True  # an invalid explicit selection cannot open another board
            self._target_serial = None
            self._jobs.clear()
            self._priority_stop = False
            self._latest = None
            self._condition.notify_all()

    @Slot()
    def disconnect_port(self):
        with self._condition:
            if self._stop or self._upgrade_busy:
                return
            self._epoch += 1
            self._desired = None
            self._connected = False
            self._suppressed = True
            self._jobs.clear()
            self._priority_stop = False
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
        if len(commands) > 1 and any(c in USB_MODE_PIDS for c in commands):
            self.message.emit("USB 模式切换需要单独提交", True)
            return
        with self._condition:
            if self._upgrade_busy:
                problem = "固件升级中；命令未排队"
            elif self._stop or not self._connected:
                problem = "设备未连接；命令未排队"
            elif commands == ['RUMBLE STOP']:
                self._priority_stop = True
                self._rumble_generation += 1
                kept = deque()
                for epoch, queued, generation in self._jobs:
                    queued = tuple(c for c in queued if not self._is_rumble_test(c))
                    if queued:
                        kept.append((epoch, queued, generation))
                self._jobs = kept
                self._condition.notify_all()
                return
            elif len(self._jobs) >= 8:
                problem = "设备操作队列已满，请等待当前操作完成"
            else:
                self._jobs.append((self._epoch, tuple(commands), self._rumble_generation))
                self._condition.notify_all()
                return
        self.message.emit(problem, True)

    @Slot(str, bool)
    def upgrade(self, path, manual=False):
        with self._condition:
            if self._stop or self._upgrade_busy:
                return
            self._upgrade_busy = True
            self._upgrade_generation += 1
            self._upgrade_events.clear()
            self._upgrade_terminal = None
            self._upgrade_cancel = False
            self._upgrade_pending = (str(path), bool(manual))
            self._jobs.clear()
            self._priority_stop = False
            self._latest = None
            self._condition.notify_all()
        self.upgrade_changed.emit(self._upgrade_state('validating', 0))

    @Slot()
    def cancel_upgrade(self):
        with self._condition:
            if self._upgrade_copying:
                return False
            self._upgrade_cancel = True
            self._condition.notify_all()
            return True

    @Slot()
    def close(self):
        with self._condition:
            if self._upgrade_copying:
                return False
            self._timer.stop()
            if not self._stop:
                self._stop = True
                self._epoch += 1
                self._connected = False
                self._jobs.clear()
                self._priority_stop = False
                self._latest = None
                self._events.clear()
                self._upgrade_events.clear()
                self._condition.notify_all()
        # pedalctl bounds each in-flight request at four seconds. The worker
        # checks cancellation between requests and closes its own link.
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=6)
        return True

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
            upgrade_events, self._upgrade_events = self._upgrade_events, deque(maxlen=64)
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
        for generation, state in upgrade_events:
            if not self._stop and generation == self._upgrade_generation:
                self.upgrade_changed.emit(state)
        if latest is not None and latest[0] == self._epoch and not self._stop:
            self.snapshot.emit(latest[1])

    def _scan(self):
        records = []
        for info in self._discover():
            if info.vid == 0xCAFE and info.pid in (0x4011, 0x4012, 0x4013):
                records.append({"device": info.device,
                                "description": info.description or "RP2350",
                                "pid": info.pid,
                                "serial_number": info.serial_number or None})
        return sorted(records, key=lambda p: p["device"])

    def _read(self, client, epoch, caps, profile, refresh, saved=False):
        def check():
            self._check(epoch)
            self._service_stop(client, epoch)
        check()
        pedal = client.get()
        check()
        if refresh and caps.get("profile"):
            try:
                profile = client.request("PROFILE")
                if not isinstance(profile, dict):
                    raise ProtocolError("Invalid PROFILE reply")
            except CommandRejected as exc:
                caps.pop("profile", None)
                profile = None
                self._event(epoch, "message", "固件不支持 PROFILE：" + str(exc), True)
        check()
        telemetry = None
        if caps.get("telemetry"):
            try:
                telemetry = client.request("TELEMETRY")
                if not isinstance(telemetry, dict):
                    raise ProtocolError("Invalid TELEMETRY reply")
            except CommandRejected as exc:
                caps.pop("telemetry", None)
                self._event(epoch, "message", "固件不支持 TELEMETRY：" + str(exc), True)
        check()
        rumble = None
        if caps.get('rumble'):
            try:
                rumble = client.request('RUMBLE')
                if not isinstance(rumble, dict):
                    raise ProtocolError('Invalid RUMBLE reply')
            except CommandRejected as exc:
                caps.pop('rumble', None)
                self._event(epoch, 'message', '固件不支持 RUMBLE：' + str(exc), True)
        check()
        return {"pedal": pedal, "telemetry": telemetry, "profile": profile,
                "rumble": rumble,
                "capabilities": dict(caps), "refresh_config": refresh, "saved": saved}

    @staticmethod
    def _is_rumble_test(command):
        return command.split()[:2] == ['RUMBLE', 'TEST']

    def _service_stop(self, client, epoch):
        self._check(epoch)
        with self._condition:
            pending = self._priority_stop
            self._priority_stop = False
        if pending:
            try:
                client.request('RUMBLE STOP')
            except CommandRejected as exc:
                self._event(epoch, 'message', '设备拒绝 RUMBLE STOP：' + str(exc), True)
        return pending

    def _upgrade_state(self, stage, progress, error='', detail=''):
        return {'stage': stage, 'progress': int(progress),
                'busy': stage not in ('complete', 'failed', 'cancelled'),
                'error': error, 'detail': detail}

    def _upgrade_event(self, epoch, stage, progress=0, error='', detail=''):
        with self._condition:
            self._upgrade_copying = stage == 'copying'
            # Upgrade lifecycle belongs to the job, not the serial connection.
            # A disconnect can advance the transport epoch before Qt drains a
            # terminal status; losing that status would leave the GUI busy.
            if not self._stop:
                event = (self._upgrade_generation,
                         self._upgrade_state(stage, progress, error, detail))
                if event[1]['busy']:
                    self._upgrade_events.append(event)
                else:
                    # Publish the terminal status only when finally releases
                    # the retry gate, atomically under the same condition.
                    self._upgrade_terminal = event

    def _upgrade_cancelled(self, epoch):
        with self._condition:
            return self._stop or self._epoch != epoch or self._upgrade_cancel

    def _perform_upgrade(self, epoch, request, link, client, caps, profile):
        """Run serial transition, transfer, and identity-bound reconnect on owner thread."""
        released = False
        try:
            path, manual = request
            image = self._updater.prepare(path)
            if self._upgrade_cancelled(epoch):
                raise UpgradeCancelled()
            target_serial = self._target_serial
            if not target_serial:
                raise ValueError('请先连接目标板卡并读取设备序列号，再手动进入 BOOT 下载模式')
            if not manual and (link is None or not caps.get('bootsel')):
                raise ValueError('此固件不支持自动 BOOTSEL；请手动进入 BOOT 下载模式后使用手动升级')
            # Snapshot existing ROM volumes before sending BOOTSEL. Automatic
            # upgrades must never pick an unrelated, already-present boot drive.
            before = self._updater.discover()
            if not manual:
                self._upgrade_event(epoch, 'entering_bootsel', 5)
                answer = client.request('BOOTSEL')
                if not isinstance(answer, dict) or answer.get('bootsel') is not True:
                    raise ProtocolError('BOOTSEL acknowledgement missing')
            if link is not None:
                link.close()
            link = client = None
            released = True
            with self._condition:
                self._connected = False
                self._latest = None
            self._event(epoch, 'connected', False, '固件升级中')
            self._updater.transfer(image, before, manual=manual,
                cancelled=lambda: self._upgrade_cancelled(epoch),
                changed=lambda stage, progress: self._upgrade_event(epoch, stage, progress))
            self._upgrade_event(epoch, 'waiting_reconnect', 100,
                                detail='传输完成；等待相同序列号设备启动，尚未确认升级成功')
            deadline = time.monotonic() + self._reconnect_timeout
            last_error = ''
            while time.monotonic() < deadline:
                if self._upgrade_cancelled(epoch):
                    raise UpgradeCancelled()
                matching = [p for p in self._scan() if p['serial_number'] == target_serial]
                if len(matching) == 1:
                    candidate = matching[0]
                    try:
                        link = self._open(candidate['device'])
                        self._check(epoch)
                        client = self._client_factory(link)
                        self._upgrade_event(epoch, 'restoring', 100)
                        try:
                            caps = client.request('CAPS')
                            if not isinstance(caps, dict):
                                raise ProtocolError('Invalid CAPS reply')
                        except CommandRejected:
                            caps = {}
                        state = self._read(client, epoch, caps, None, True)
                        if self._upgrade_cancelled(epoch):
                            raise UpgradeCancelled()
                        profile = state['profile']
                        with self._condition:
                            self._check(epoch)
                            self._connected = True
                            self._suppressed = False
                        self._event(epoch, 'connected', True, candidate['device'])
                        self._publish(epoch, state)
                        self._upgrade_event(epoch, 'complete', 100,
                            detail='UF2 传输完成，已重读目标设备状态；设备报告版本：' +
                                   str(caps.get('version') or '未知') + '；未做 Flash 逐字节回读')
                        return link, client, caps, profile
                    except _Cancelled:
                        raise UpgradeCancelled()
                    except UpgradeCancelled:
                        if link is not None:
                            link.close()
                        link = client = None
                        raise
                    except Exception as exc:
                        last_error = str(exc)
                        if link is not None:
                            link.close()
                        link = client = None
                with self._condition:
                    self._condition.wait(timeout=0.05)
            raise TimeoutError('UF2 已传输，但目标设备未重新连接并读取状态：' + last_error)
        except UpgradeCancelled:
            self._upgrade_event(epoch, 'cancelled', detail='已取消；若设备停留在 BOOT 模式，可手动重试')
        except Exception as exc:
            self._upgrade_event(epoch, 'failed', error=str(exc),
                                detail='请检查 UF2/连接；可按住 BOOT 重新接入并手动重试。不会自动再次写入')
        finally:
            with self._condition:
                self._upgrade_busy = False
                self._upgrade_copying = False
                self._upgrade_pending = None
                self._jobs.clear()
                # Allow only the captured board to reconnect after a failed or
                # cancelled transfer. No settings, SAVE or test commands replay.
                if released:
                    self._suppressed = not bool(self._target_serial)
                if self._upgrade_terminal is not None and not self._stop:
                    self._upgrade_events.append(self._upgrade_terminal)
                self._upgrade_terminal = None
        return link, client, caps if link is not None else {}, profile if link is not None else None

    def _failed(self, epoch, error):
        self._end_connection(epoch, "连接已关闭", "串口连接失败：" + str(error), True)

    def _end_connection(self, epoch, description, message, error=False):
        with self._condition:
            if self._stop or epoch != self._epoch:
                return
            self._epoch += 1
            self._connected = False
            self._desired = None
            self._jobs.clear()
            self._priority_stop = False
            self._latest = None
            self._suppressed = not bool(self._target_serial)
            self._events.append((self._epoch, "connected", (False, description)))
            self._events.append((self._epoch, "message", (message, error)))
            return self._epoch

    def _run(self):
        link = client = None
        local_epoch = -1
        caps, profile, records = {}, None, []
        next_scan = next_poll = 0.0
        previous_ports = None
        usb_switch = None
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
                with self._condition:
                    upgrade_request = self._upgrade_pending
                if upgrade_request is not None:
                    link, client, caps, profile = self._perform_upgrade(
                        epoch, upgrade_request, link, client, caps, profile)
                    next_scan = 0
                    next_poll = time.monotonic() + self._poll_interval
                    continue
                now = time.monotonic()
                if usb_switch:
                    switch_epoch, expected_pid, deadline = usb_switch
                    if switch_epoch != epoch:
                        usb_switch = None
                    elif now >= deadline:
                        usb_switch = None
                        self._event(epoch, "message", "等待新 USB 模式超时，正在重新识别设备", True)
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
                            if usb_switch:
                                matching = [p for p in matching if p["pid"] == expected_pid]
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
                            if usb_switch:
                                usb_switch = None
                                self._event(epoch, "message", "USB 模式已切换。回零后可保存到 Flash", False)
                            next_poll = time.monotonic() + self._poll_interval
                        except _Cancelled:
                            continue
                        except Exception as exc:
                            self._failed(epoch, exc)
                            continue
                if link is not None:
                    try:
                        self._check(epoch)
                        self._service_stop(client, epoch)
                        with self._condition:
                            batch = self._jobs.popleft() if self._jobs else None
                        if batch is not None:
                            batch_epoch, commands, rumble_generation = batch
                            self._check(batch_epoch)
                            saved = False
                            rejected = False
                            switching = False
                            for command in commands:
                                self._check(epoch)
                                self._service_stop(client, epoch)
                                with self._condition:
                                    if self._upgrade_busy:
                                        break
                                    stale_test = (rumble_generation != self._rumble_generation and
                                                  self._is_rumble_test(command))
                                if stale_test:
                                    continue
                                try:
                                    answer = client.request(command)
                                    if command in USB_MODE_PIDS:
                                        if not isinstance(answer, dict) or type(answer.get("usb_switch")) is not bool:
                                            raise ProtocolError("USB mode acknowledgement missing")
                                        if answer["usb_switch"]:
                                            new_epoch = self._end_connection(
                                                epoch, "正在切换 USB 模式", "等待同一开发板重新连接")
                                            if new_epoch is not None:
                                                usb_switch = (new_epoch, USB_MODE_PIDS[command],
                                                              time.monotonic() + self._reconnect_timeout)
                                                next_scan = 0
                                            switching = True
                                            break
                                    saved |= command == "SAVE"
                                except CommandRejected as exc:
                                    rejected = True
                                    self._event(epoch, "message", "设备拒绝 " + command + "：" + str(exc) + "；连接保持", True)
                                    break
                            if switching:
                                continue
                            with self._condition:
                                if self._upgrade_busy:
                                    continue
                            self._service_stop(client, epoch)
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
                    if (self._stop or epoch != self._epoch or self._jobs or self._desired is not None or
                            self._upgrade_pending or self._priority_stop):
                        continue
                    deadline = min(next_scan, next_poll) if link is not None else next_scan
                    self._condition.wait(timeout=max(0, deadline - time.monotonic()))
        finally:
            if link is not None:
                link.close()
