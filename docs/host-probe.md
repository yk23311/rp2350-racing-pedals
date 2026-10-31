# USB-A Host 桥接使用与诊断

更新：2026-10-31。`-UsbMode host`现在构建完整桥接，已经合并摇杆、按键和踏板，**不是旧Host-only探针**。最新修复版0.3.1尚未烧录或实机验收。见[步骤/交接报告](reports/13-bridge-review-fixes.md)。

## 日常使用

1. 关闭GUI，断开板卡Type-C；按住BOOT连接电脑，出现BOOTSEL磁盘后释放。
2. 将`dist/host/pedals-host.uf2`复制进去，等待自动重启。普通更新应保留Flash校准，不要整片擦除。
3. Type-C接电脑，真实手柄2.4G接收器插开发板USB-A，接收器不要另插电脑。GP26/27踏板接线不变。
4. 松开踏板、手柄扳机和按键，摇杆回中，等待恢复。默认MAX：RT/LT各取踏板和手柄较大值，松开某一输入不会抵消另一输入。
5. 双击根目录`启动调参GUI.bat`，选择实际串口（可能是COM8），连接、校准、应用参数。释放踏板及真实手柄按钮/扳机，等待回零后保存。摇杆轻微漂移不会阻止SAVE。
6. 由用户确认FH6的Steam Input关闭；游戏不需要GUI或脚本常驻。

硬件改动状态及电流预算仍待确认。微雪官方对R13的要求见[Wiki](https://www.waveshare.com/wiki/RP2350-USB-A)。本次修复没有拆焊或修改电气接线；短时收包不替代热插拔、电气验收。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode host
```

普通版产物`dist/host/pedals-host.uf2`，默认关闭Host日志；每次构建自动刷新同目录manifest中的大小/SHA256，明确重置为未烧录、未实机验证。只保留旧独立踏板时可回退`dist/xinput/pedals-xinput.uf2`。

## 专用诊断版

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode host -HostDiagnostics
```

诊断版位于`dist/host-debug/pedals-host.uf2`，与普通版分开。需要排查时才烧录该文件；它仍是完整桥接，只是额外输出异步`[HOST]`日志。诊断版不作为可靠调参基线：旧日志与命令回复可能在字节层交错；新的客户端只能跳过完整日志行，不会猜测修复损坏的数据。

关闭GUI后运行（不能同时占用串口）：

```powershell
.\.venv\Scripts\python.exe tools/host_probe.py --list
.\.venv\Scripts\python.exe tools/host_probe.py --port COM8 --seconds 60 --output docs/reports/logs/host-new-live.txt
```

按实际串口替换COM8。查看mount/interface/handshake/pad/state/timeout记录；普通版不输出这些日志，所以读不到日志不能认定Host失效。state=3为STREAMING。异步日志不构成命令回复。

## 尚待执行的实机验收

- 同一个XInput槽位同时满足`LX != 0 && RT > 0`，以及`LX != 0 && LT > 0`；再检查ABXY/方向键/肩键与双踏板同时输入。
- GUI连接、持续读取、应用/校准/SAVE及重启后保留；当前0.3.1二进制没有实测证据。
- 拔插接收器、手柄关机及回连、保存Flash后Host恢复、至少1小时稳定性、FH6驾驶。

可用`tools/check_xinput.py --seconds 30`只读记录Windows输入；至少同时保持转向和踏板数秒，不能只分开操作。旧日志仅能证明旧版本单项输入，不能替代本轮验收。
