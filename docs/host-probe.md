# Host 探针使用说明

本固件只用于验证 RP2350 的 USB-A 是否能读取 20BC:5128 接收器，**不合并输入、不改硬件、不替代最终桥接固件**。设备端仍只输出原来的踏板 XInput 手柄；电脑上仍应只看到 `CAFE:4012`。

## 构建产物

- `dist/host/pedals-host.uf2`：Host 探针固件，未烧录。
- `dist/host/pedals-host.elf`、`.bin`、`.elf.map`：调试/校验用。
- 当前探针使用 Pico-PIO-USB **0.7.2 tag**，Pico SDK 2.2.0，TinyUSB 0.18.0；未拆 R13、未改任何硬件。

## 烧录

1. 断开开发板 Type-C。
2. 按住 BOOT，连接 Type-C，释放 BOOT；出现 `RP2350` 或 `RPI-RP2` 磁盘。
3. 把 `dist/host/pedals-host.uf2` 复制到该磁盘，等待自动重启。
4. 若探针导致板子无响应：断开 Type-C，按住 BOOT 重新进入 BOOTSEL，刷回 `dist/xinput/pedals-xinput.uf2`。

## 接线与测试

1. Type-C 继续接电脑；**不要**把接收器插在电脑上。
2. 把北通 2.4G 接收器插入开发板 USB-A（当前 R13 未拆，可能无法枚举；这正是要验证的）。
3. 手柄开机并切到 2.4G/接收器模式。
4. 打开串口（通常仍是 COM8，可能在设备管理器变化），运行：

```powershell
Set-Location -LiteralPath 'D:\练习项目\RP2350a'
.\.venv\Scripts\python.exe tools/host_probe.py --list
.\.venv\Scripts\python.exe tools/host_probe.py --port COM8 --seconds 30 --output docs/reports/logs/host-probe-live.txt
```

5. 观察 `[HOST]` 行，重点记录：
   - `mount` / `xinput interface`：USB-A 是否枚举到接收器；
   - `handshake` / `compat`：XUSB10 请求是否成功；
   - `pad n=...`：是否收到 20 字节报告，摇杆/按键/扳机是否随操作变化；
   - `state=...`、`umount`：是否反复断开/重枚举。

## 判定

- **有 mount + xinput interface + pad 行**：现有硬件（R13 未拆）也能读到接收器；继续做合并接线。
- **有 mount 但没有 xinput interface**：接收器枚举成了别的接口/模式；保存日志后分析，不要直接改合并代码。
- **完全没有 mount**：R13 上拉导致 Host 不可用，或 USB-A 供电/接线问题；需要后续硬件核实（本轮不拆）。
- **mount 后约 1–2 秒 umount/重枚举，或出现 `057E:2069`/`20DD`**：接收器的模式锁定握手不完整；保存日志，再补 GIP/OS 字符串等 A/B，不要先改合并。

本工具只读串口，不发送命令、不注入按键、不做电脑端映射。
