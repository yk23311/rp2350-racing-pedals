# 12 Host 探针构建：步骤与交接

日期：2026-10-31。状态：**Host-only 探针固件已构建成功，尚未烧录、尚未上板验证；未修改任何硬件。** 当前板卡仍应运行旧的 `0.2.0-xinput` 固件。

## 步骤报告

1. 在 Git 基线之后，固定并下载 **Pico-PIO-USB tag `0.7.2`**（不是不可复现的“v0.7.3”），解压到 `deps/Pico-PIO-USB`；`tools/fetch_deps.py` 已加入同一固定 tag 的下载与解压。
2. 解决 SDK 生成 PIO 头所需的宿主 `pioasm`：新增 `tools/build_pioasm.ps1`，用已安装的 Clang/LLD 构建并安装到 `build/pioasm-install`；`tools/build_firmware.ps1` 在 `-UsbMode host` 时自动引导，并传入 `-Dpioasm_DIR=...`。
3. 增加 `PEDAL_USB_HOST` 构建选项（默认 OFF），只在 host 模式启用：
   - `PICO_PIO_USB_PATH` 指向 `deps/Pico-PIO-USB`；
   - 链接 `tinyusb_host`、`tinyusb_pico_pio_usb`；
   - `firmware/tusb_config.h` 打开 `CFG_TUH_ENABLED/CFG_TUH_RPI_PIO_USB`，设置 `CFG_TUH_DEVICE_MAX=1`、`CFG_TUH_ENUMERATION_BUFSIZE=512`、`CFG_TUH_INTERFACE_MAX=8`；
   - 单核 host 构建定义 `PICO_FLASH_ASSUME_CORE1_SAFE=1`，避免 `pico_multicore` 使 `storage_save()` 返回 `PICO_ERROR_NOT_PERMITTED`。
4. 新增 `firmware/host.c/h`：
   - `host_init()` 先设置 `PIO_USB_DEFAULT_CONFIG.pin_dp=12`，调用 `tuh_configure(1, ...)`，再 `tusb_init(1, host)`；设备端 `usb.c` 在 host 构建中显式 `tusb_init(0, device)`；
   - 自定义最小 XInput Host 类：匹配 FF/5D/01、解析并打开 IN/OUT 端点、IN 端点始终重挂；
   - `tuh_mount_cb` 只对已打开 XInput 接口的设备建立 `bridge` 状态；20BC 设备依次尝试 XUSB10 `0xC0/0xEE/0/4/40`、失败回退 `0x20`，再发 magic `0xC1/0x01/0x100/0/20`；
   - 控制传输由 `host_task()` 异步推进，不在完成回调里递归发起下一次传输；
   - CDC 输出 `[HOST]` 诊断行：mount/interface/handshake/compat 原始字节/前 8 帧报告/每 250 帧/500ms 状态；不改变 Device 端 XInput 报文。
5. `firmware/main.c` 在 host 构建中先 `set_sys_clock_khz(120000, true)`，初始化后调用 `host_init()`，主循环调用 `host_task()`；Device-only 构建仍为 150 MHz。
6. 构建结果：host 探针 `dist/host/pedals-host.uf2` 共 140,288 字节，BIN 69,912 字节，SHA256 `E1536CF02B4B321808CB2DC87DF9897A095765B1C447C288E9B52D572EDAC8D8`；`__flash_binary_end=0x10011118`，远低于配置区 `0x101FE000`。
7. 回归构建 device-only XInput 成功，text 44,292 / bss 5,192；由于加入 `xinput_axis_quantize()`，旧产物哈希会变化，不能继续引用旧 SHA 作为本次产物证据。

## 验证状态

**已做：**

- host 探针交叉编译、链接通过；`hcd_pio_usb.c`、Pico-PIO-USB、TinyUSB host 源均参与构建；
- 自定义 Host 类和握手代码编译通过；
- 29 项 CTest + 19 项 Python 仍通过（纯 C 核心，不覆盖真实 Host 枚举）。

**未做（必须板级验证）：**

- 没有烧录 host 探针；
- 没有把接收器从电脑移到开发板 USB-A；
- 没有在 R13 未拆的情况下验证枚举/握手/报告；
- 没有验证 120 MHz、PIO-USB 1 ms timer、SAVE/flash 与 Host 共存；
- 没有合并到 Device 输出。

## 使用与判定

见 `docs/host-probe.md`。核心步骤：烧录 `dist/host/pedals-host.uf2`，Type-C 接电脑，接收器插开发板 USB-A，手柄开机，运行：

```powershell
.\.venv\Scripts\python.exe tools/host_probe.py --port COM8 --seconds 30 --output docs/reports/logs/host-probe-live.txt
```

判定：

- 有 `mount` + `xinput interface` + `pad n=...`：现有硬件可读，继续做合并接线；
- 有 mount 但无 XInput 接口：枚举成别的模式，保存日志再分析；
- 完全没有 mount：R13/供电/接线问题，需后续硬件核实（本轮不拆）；
- mount 后 1–2 秒掉线或出现 `057E:2069`/`20DD`：模式锁定握手不完整，保存日志后再补 GIP/OS 字符串 A/B。

## 交接报告

Host 探针的软件链路已经打通到“可编译、可生成 UF2”的阶段，但**尚未证明能在现有硬件上读取接收器**。下一步不是写合并，而是由用户执行一次烧录 + 插接收器 + 串口日志采集；根据 `[HOST]` 日志决定是继续合并、补握手，还是先处理 R13/供电。若探针导致板子无响应，按住 BOOT 刷回 `dist/xinput/pedals-xinput.uf2`；不得把本轮构建当成桥接可用或游戏验收通过。
