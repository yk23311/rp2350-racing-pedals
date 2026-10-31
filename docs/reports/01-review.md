# 01 方案审核：步骤与交接

日期：2026-10-30。状态：软件方向通过；电气接入有前置条件。

## 步骤报告

1. 检查工作目录：初始为空，无 AGENTS.md、既有代码、Git 仓库。
2. 确认用户硬件：微雪 RP2350-USB-A、两个踏板、传感器 5V 供电。
3. 官方原理图核对：Type-C 原生 USB；USB-A 为 GP12/13 PIO；GP26/27 可作 ADC0/1；Flash W25Q16 为 2 MiB。
4. 比较 Pico SDK、Arduino、MicroPython，采用 Pico SDK 2.2.0 + 配套 TinyUSB，单核实现。
5. 写入设计及计划，按用户已授权的“审核后实施”继续推进。

## 必须修正的原方案内容

| 原说法 | 审核结果 |
|---|---|
| 霍尔必须分压 | 根据输出范围决定；5V供电本身不足以确定输出；未测量不得直连 |
| 改分压拓扑反向 | 普通正电阻分压不能反向，软件用 released/pressed 两端点 |
| HID 避免被游戏识破 | 实现标准 HID，但 HID 不等于 XInput，不承诺所有游戏兼容 |
| 0–65535 高精度 | RP2350 ADC 原始12位，映射16位不增加测量精度 |
| 动态学习上下限 | 仅显式校准模式学习，正常运行冻结；跨度过小拒绝 |
| 一阶滤波必然高延迟 | 延迟取决于参数和采样率；首版短窗口平均，实测再调 |
| 刹车必须指数曲线 | gamma 可调，默认2.00，也允许线性；随机械结构和游戏调校 |
| 保存 JSON 即可靠 | 使用版本+CRC+双槽，显式SAVE；电脑侧导出JSON |
| 双核分别操作USB | 首版USB统一单核调度，避免不必要并发 |
| AS5600 读AB相 | AS5600为单圈绝对角度，I2C/模拟/PWM；AB需正交编码器 |
| 工业级 | 尚无硬件、EMC、可靠性、USB合规等证据，当前定位开发原型 |

## 交接报告

下一阶段输入：已冻结的首版设计。可以实施纯C核心、协议、板型适配。接线仍需传感器型号或实测输出类型/电压/线序，5V电源可提供的电流也需要核对。屏幕、方向盘、震动和宏后续单独设计。

资料：
- [微雪原理图](https://files.waveshare.com/wiki/RP2350-USB-A/RP2350-USB-A.pdf)
- [SDK板定义](https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/boards/include/boards/waveshare_rp2350_usb_a.h)
- [SDK硬件API](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html)
- [SDK Flash安全执行](https://www.raspberrypi.com/documentation/pico-sdk/high_level.html#pico_flash)
- [TinyUSB](https://docs.tinyusb.org/en/latest/)
- [Microsoft XInput与DirectInput](https://learn.microsoft.com/en-us/windows/win32/xinput/xinput-and-directinput)
- [AS5600手册](https://look.ams-osram.com/m/7059eac7531a86fd/original/AS5600-DS000365.pdf)
