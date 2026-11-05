# GUI 测试与升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 交付可测试真实按键、限时震动并自动写入 UF2/重连的控制中心。

**Architecture:** 沿用 Qt 主线程和 Session 单串口工作线程；升级文件/磁盘操作隔离到 firmware_update.py。板端提供 RUMBLE TEST/STOP 和延迟 BOOTSEL，沿用现有中立屏障、停止优先与配置扇区边界。

**Tech Stack:** Python/PySide6/pyserial；Pico SDK 2.2.0、TinyUSB、C11、UF2、Windows removable drives。

## Global Constraints

- 固件版本 0.5.0，板卡 RP2350-USB-A、RP2350 ARM-S family 0xE48BFF59。
- 禁止写入 0x101FE000–0x10200000；不整片擦除，不使用 Steam/电脑虚拟映射。
- 测试震动 0–255 两马达、100–3000ms；默认界面 25%、500ms，板端到时停止。
- 现有 0.4.1 本地震动修复保留；不自动烧录、不覆盖公共 Release。
- 所有串口 IO 由 Session 线程拥有，重连不重放设置/SAVE/测试命令。

### Task 1: UF2 与升级工作流

**Files:** 新建 tools/firmware_update.py、tests/test_firmware_update.py；修改 tools/control_session.py、tests/test_control_session.py。

**Interfaces:** Session.upgrade(path: str, manual: bool=False)；upgrade_changed(dict) 信号，字段 stage/progress/busy/error/detail。snapshot 增加 rumble 可选字典。firmware_update 暴露 validate_uf2(data: bytes)、discover_boot_drives()、执行器（IO 可注入）。

- [x] 先测合法镜像和错误 family/魔数/缺块/重复/越界；自动模式排除既有盘，多盘拒绝，手动模式唯一盘；取消前不写，写入后等待相同 serial 重连。

```python
data = convert(bytes(512))
image = validate_uf2(data)
self.assertEqual(image.blocks, 2)
bad = bytearray(data); bad[28:32] = (0).to_bytes(4, 'little')
with self.assertRaises(ValueError): validate_uf2(bytes(bad))
```

- [x] `.venv/Scripts/python.exe -m unittest tests.test_firmware_update -v` 观察缺失功能失败，再实现严格校验、Windows 盘检测、分阶段写入和串口生命周期。
- [x] 加入能力协商、旧固件提示、升级独占、失败恢复和 RUMBLE 状态读取；模拟 BOOTSEL 拒绝/磁盘超时/断线不误报成功。
- [x] 运行新模块与 Session 全部测试，记录结果。

### Task 2: 测试与升级页面

**Files:** 新建 tools/control_test_pages.py、tests/test_control_test_pages.py；修改 tools/control_center.py、tests/test_control_gui.py。

**Interfaces:** 接入 Task 1 的 Session.upgrade/upgrade_changed；Session.submit(["RUMBLE TEST 64 64 500"])、Session.submit(["RUMBLE STOP"])。读取 snapshot.capabilities 的 rumble_test/bootsel、snapshot.rumble；仅 fresh 原始输入完成按键测试。

- [x] 先测完整按下/松开、过期中断不能算松开、换板清空、演示不写板、旧固件禁用震动及自动升级。

```python
page.update_buttons(1 << 12, True)
page.update_buttons(0, False)
self.assertFalse(page.completed_mask & (1 << 12))
page.update_buttons(0, True)
self.assertFalse(page.completed_mask & (1 << 12))
```

- [x] `.venv/Scripts/python.exe -m unittest tests.test_control_test_pages -v` 先观察失败，再实现两页卡片、状态提示、UF2 选择/摘要/进度和按钮状态。
- [x] 升级忙时禁止调参/测试/断开，写入阶段阻止关窗；保留现有四页行为。
- [x] Qt 测试通过后生成两个新页面的演示截图，检查中文、缩小窗口和禁用提示。

### Task 3: 板端命令与停止/升级屏障

**Files:** firmware/host.{c,h}、firmware/usb.{c,h}、firmware/main.c、firmware/CMakeLists.txt、tools/write_manifest.py；tests/test_rumble_host.c、tests/test_bridge_usb.c、CMakeLists.txt。

**Interfaces:** bool host_rumble_test(uint8_t left,uint8_t right,uint32_t duration_ms)；host_rumble_status_t 新增 testing/remaining_ms。RUMBLE TEST l r ms 严格接受完整范围；RUMBLE STOP 始终允许；BOOTSEL 仅 Host 版公布能力。USB 层导出升级 pending/ready 查询，main 在 ACK 排空且中立/停震等待完成后调用 ROM reset。

- [x] 先加 Host 定时、游戏命令隔离、显式停止、断线、时钟回绕测试。

```c
CHECK(host_rumble_test(64,32,500));
now+=501;tick();host_rumble_status(&status);
CHECK(!status.testing && !status.left && !status.right);
```

- [x] 加 USB 命令解析/CAPS/BOOTSEL 强制中立测试，观察新断言失败，再实现；升级不写配置，不允许后续设置打断 pending。
- [x] 普通/诊断构建版本更新为 0.5.0，确保链接仍避开配置扇区。

### Task 4: 联合验证与交接

**Files:** docs/control-center.md、docs/protocol.md、docs/reports/18-gui-tests-updater.md、docs/reports/00-handoff.md、HANDOFF.md、artifacts/、dist/gui-upgrade/。

- [x] `powershell -ExecutionPolicy Bypass -File tools/build_host.ps1`：全部 C/Python 通过，保存日志。
- [x] `powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode host` 和 `-HostDiagnostics`：构建成功，校验 UF2 与 manifest/hash。
- [x] 离屏检查六页与最小窗口；独立审查升级生命周期/失败处理和板端命令；修复确定问题后重跑对应测试。
- [x] 记录实机尚未验证，交付首次手动烧录、后续一键升级、按钮和震动测试步骤与恢复办法。

完成记录：2026-11-05。58项CTest、109项Python通过；两个固件构建/哈希校验完成，步骤与交接见 docs/reports/18-gui-tests-updater.md。未刷入硬件或推送Release。
