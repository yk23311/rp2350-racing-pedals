# 11 软件桥接核心：步骤与交接

日期：2026-10-31。状态：**纯 C 的 XInput Host 报文解析与踏板/手柄合并核心已完成并通过 PC 测试；Host USB 栈、能力查询和固件接线尚未开始。** 本轮未修改任何硬件。

## 步骤报告

1. 检查发现工程没有 Git 仓库；在项目根目录执行 `git init -b main`，配置本地提交身份，建立基线提交 `6fa0512`（89 个文件，10,689 行）。`deps/`、`build/`、`.venv/`、`dist/` 按现有 `.gitignore` 排除。
2. 在基线状态运行 `tools/build_host.ps1`，确认原有 **18 项 CTest + 19 项 Python 全部通过**，日志见 `docs/reports/logs/software-baseline-host.txt`。
3. 新增 `include/xinput_pad.h`、`src/core/xinput_pad.c`：严格解析标准 Xbox 360 有线 20 字节报告（`00 14 ...`），解析按键、LT/RT、四个 int16 小端摇杆；拒绝短包、错误报告 ID/长度；提供整份中立与“按键/扳机受控中立”谓词。
4. 新增 `include/bridge.h`、`src/core/bridge.c`：Host 状态机（ABSENT/ENUMERATING/HANDSHAKING/STREAMING/STALE）、250 ms 超时、250 ms 重连回中门控、踏板优先 OVERRIDE 与 MAX 两种策略、Host 曾连接/从未连接两种故障行为、20 字节输出构造。
5. 在 `include/xinput_protocol.h`、`src/core/xinput_protocol.c` 增加 `xinput_axis_quantize()`，复用现有 `(value+128)/257` 映射；现有 `xinput_report_build()` 改为调用该函数，行为不变。
6. 新增 `tests/test_xinput_pad.c`（parse/neutral/predicates）和 `tests/test_bridge.c`（pedal_only/handshake/override/max/timeout/unmount/blocked/quantize），共新增 11 项 CTest。
7. 运行完整主机测试：**29 项 CTest 全部通过，19 项 Python 全部通过**，日志见 `docs/reports/logs/software-bridge-core.txt`。

## 实现内容

### 解析

- 有效帧：`len >= 20`、`data[0] == 0x00`、`data[1] == 0x14`。
- 字段：buttons `[2..3]` u16 LE，LT `[4]`，RT `[5]`，LX/LY/RX/RY `[6..13]` int16 LE。
- 拒绝帧不修改输出结构；扫描/保留字节不参与解析。

### 合并状态机

- 初始 `ABSENT`；`host_seen` 是“自开机以来见过 Host”的锁存位。
- mount → `ENUMERATING`；握手完成 → `HANDSHAKING`；连续 2 帧有效且回中 → `STREAMING`。
- 250 ms 无有效报告 → `STALE`，清空 pad；新报告回到 `HANDSHAKING`，重新要求 2 帧回中。
- 回中容差 `abs(LX/LY/RX/RY) <= 4000`，且 buttons/LT/RT 为 0；实测静止值 `LX=-928、LY=704` 在容差内。
- `host_seen == false` 时保持踏板单独输出；`host_seen == true` 但非 STREAMING 时默认整只全中立（含踏板）。
- `OVERRIDE`：踏板轴已校准时完全拥有 RT/LT；未校准轴回退真实手柄扳机。`MAX` 仅作 RAM 选项，默认不启用。
- 报告门控/键盘模式/校准中/`pedal` 未 armed/采样无效时输出全中立（保留 `report[1]=20`）。

## 验证证据

- Git：`6fa0512` 基线；本阶段提交见 `git log`。
- 主机日志：`docs/reports/logs/software-bridge-core.txt`。
- CTest：29/29 通过；Python：19/19 通过。
- 未重新构建/烧录固件；`firmware/xinput_device.c`、`firmware/usb.c`、`firmware/main.c` 未改动。

## 未完成 / 下一阶段

1. **P1 Host-only 探针**：vendor Pico-PIO-USB、TinyUSB Host 双 rhport、最小 XInput Host 类、XUSB10/GIP 握手 A/B、CDC 原始报文；先验证 20BC:5128 能否稳定读取。
2. **P3 能力查询**：当前 `xinput_control_response()` 仍只声明 LT/RT；桥接固件必须新增完整按键/摇杆/扳机能力声明并测试。
3. **固件接线**：`usb.c` 的 `make_report(0)` 尚未调用 `bridge_build_report()`；`main.c` 尚无 `tuh_task()`；单核 flash 安全配置尚未处理。
4. **硬件**：R13、USB-A VBUS/电流、15 kΩ 下拉按用户要求暂不修改，留待板级实测。

## 交接报告

本轮建立了可回退的 Git 基线，并完成与 USB 无关、可在 PC 上完全测试的解析/合并核心。下一步先做 Host-only 探针，**不合并、不改硬件**，以确认接收器在现有板卡（R13 未拆）上是否能枚举并读出 20 字节报告；如果现有硬件条件下不可用，再决定是否需要进行 R13 等硬件改动。合并核心已就绪，但尚未接入固件，不能把本轮测试当作“桥接可用”或“游戏验收通过”。
