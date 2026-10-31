# RP2350 双踏板：接手入口

更新：2026-10-31，Asia/Shanghai。工作目录：`D:\练习项目\RP2350a`。已建立Git仓库；软件桥接核心已完成并通过PC测试，Host USB栈、能力查询和硬件改动尚未开始。最新阶段报告：[11 软件桥接核心](docs/reports/11-software-bridge-core.md)。本文件是最新状态摘要，优先于旧报告中的阶段性结论。

## 1. 用户当前目标与授权边界

目标是在 **Steam版《极限竞速：地平线6》** 中，同时使用真实手柄转向/按键与两个踏板：GP26油门作为RT，GP27刹车作为LT。

用户明确要求：

- 开发板必须通过USB原生识别为手柄。
- **不要Steam Input、虚拟手柄、电脑端第三方输入转换。** 串口GUI仅用于校准和调参，可以保留。
- 每阶段需要步骤报告和交接报告。
- 用户已批准**先从软件开始**：先建Git仓库、实现并测试板端合并软件；**明确暂不修改硬件**（R13、15k下拉、VBUS等均未动）。
- 当前仍禁止Steam Input、电脑端虚拟手柄和电脑端第三方输入转换；接收器最终必须从电脑移到开发板USB-A。
- 本轮已进入实施，不再是纯交接；每阶段继续更新步骤报告和交接报告。

## 2. 已完成、已上板验证的部分

项目原先为空，现已具备：

- Pico SDK C11固件；纯C滤波、校准、方向映射、迟滞死区、幂曲线。
- GP26/ADC0油门、GP27/ADC1刹车，1ms目标采样周期；可选GP14长按切换逻辑模式。
- 显式校准BEGIN/END/CANCEL，跨度至少128 ADC counts；正常运行不自动学习端点。
- 默认触发3%/释放1%，平均窗口4，油门gamma1.0、刹车gamma2.0；实际用户可能已调整并保存。
- Flash版本/CRC/双槽保存，末尾两个4KiB扇区保留；显式SAVE，未校准中立、切换模式回零重新使能。
- CDC命令行与Tkinter调参GUI；`.venv`已安装pyserial3.5。
- **原生USB XInput**，不依赖电脑映射器；独立键盘HID、CDC保留。
- **Git仓库**：2026-10-31初始化，基线提交`6fa0512`；此后按阶段提交，不再“没有Git历史”。
- **软件桥接核心（未接线）**：`src/core/xinput_pad.c`严格解析20字节XInput Host报文；`src/core/bridge.c`实现Host状态机、250ms超时、回中容差4000、踏板优先OVERRIDE/MAX和20字节合并构造；PC测试29项CTest通过。尚未接入固件，接收器仍不能读取。

当前已烧录版本：**0.2.0-xinput**。

| 项目 | 已确认值 |
|---|---|
| 开发板 | 微雪 Waveshare RP2350-USB-A，2MiB外置Flash |
| PC连接 | Type-C原生USB |
| 设备VID/PID | 开发身份 `CAFE:4012`，不使用微软VID |
| 接口0 | FF/5D/01，微软OS兼容ID `XUSB10`，Windows内置`xusb22` |
| Windows显示 | “支持 Windows 的 XBOX 360 手柄”，Status OK |
| 当前观察到的CDC | COM8（可能变化，之前旧HID是COM7） |
| 游戏输入报文 | 20字节，GP27→LT offset4，GP26→RT offset5，各0–255 |
| 其他游戏输入 | 四个摇杆轴和所有按钮均0，当前固件没有真实手柄数据来源 |
| 当前USB-A功能 | **未启用Host，不能读取接收器** |

真实实测：用户已烧录，查询到内置xusb22服务及`USB\MS_COMP_XUSB10`；独立进程调用系统`xinput1_4.dll`的XInputGetState成功。30秒590个样本中，LT与RT均覆盖0–255，出现只RT、只LT、同时255和全松开0；按钮与摇杆始终中立。

证据：

- [原生XInput步骤/交接](docs/reports/10-native-xinput.md)
- [实机采样](docs/reports/logs/native-xinput-live.json)
- [当前产物清单](dist/xinput/manifest.json)
- [原生使用说明](docs/native-xinput.md)

**这些证据只证明独立踏板手柄成功，不能证明与真实手柄合用或游戏验收通过。**

## 3. 当前真实问题与只读取证

用户反馈：踩油门时真实手柄不能转向；转向时踏板不能加速。

只读查询确认电脑同时存在两只正常的XInput设备：

| 设备 | 标识/状态 |
|---|---|
| 踏板板卡 | CAFE:4012，xusb22；观察到槽位0：RT=255、摇杆全0 |
| 真实手柄接收器 | **BTP-KP20 XINPUT**，`VID_20BC&PID_5128&MI_00`，xusb22，兼容ID XUSB10、接口FF/5D/01；观察到槽位1：LX=-928、LY=704，RT/LT=0 |

用户确认真实手柄通过 **2.4G USB接收器** 连接电脑。不要再询问它是有线、蓝牙还是2.4G；这一信息已经确认。具体商品型号未由用户给出，以USB设备名和VID/PID为实现依据。

当前判断：游戏未将两个独立控制器的状态合成同一玩家输入，表现为设备切换/抢输入。不要再尝试用调整死区、给设备相同名称/VID/PID、重排槽位来声称完成输入合并。

## 4. 已向用户提出的下一阶段方案（尚未实现）

```text
真实手柄 --2.4G--> USB接收器
                         │
                   开发板 USB-A（Host）
                         │ 手柄摇杆/按键
GP26油门 ----------------┤ RT
GP27刹车 ----------------┤ LT
                         ▼
                板端合成一个完整XInput报文
                         │ Type-C（Device）
                         ▼
                   电脑只收到一只完整手柄
```

接收器从电脑移到开发板USB-A；真实手柄无线链路保持不变。板端读取其XUSB10输入，将摇杆、方向键、ABXY等透传，RT/LT由踏板覆盖。每份发给PC的报文同时包含全部状态，解决当前互相抢输入的问题。

建议行为：

- 默认踏板优先，真实手柄RT/LT不再直接控制这两项；若要支持max合并，应先讨论具体需求，不暗改策略。
- 接收器拔出或手柄通信超时，完整输出中立；重连后回零再恢复。
- 接收器仍在但无线手柄关闭时，需根据协议状态/输入超时处理，不能只依赖USB拔出事件。
- 先保证输入桥接，再考虑把游戏震动命令回传真实手柄；当前固件只消费震动命令，没有真实马达输出。
- 游戏运行不依赖电脑常驻程序，调参GUI依旧只是配置工具。

## 5. 实施前必须核实的工程点

1. **USB-A硬件/R13：** 微雪官方明确说明PIO-USB Host热插拔需要移除R13，移除后该PIO口不能作为Device。当前R13是否已移除、实际板卡修订均未确认；没有让用户拆除，没有执行硬件改动。
2. USB-A采用GP12 D+、GP13 D−；Type-C是RP2350原生USB。不要反过来，不需要把两个口都接电脑。
3. 核对USB-A的5V供电、接收器功耗、现有传感器负载和USB声明的电流预算。当前描述符声明100mA；加入Host后不能不经核算直接照旧或任意提高。
4. 可参考Pico-PIO-USB的RP2350 Host能力；其FS/LS支持不意味着能读取所有高速或专用接收器，需确认此接收器实际枚举及报告。
5. 这只接收器在电脑端是XUSB10厂商接口，不能仅增加普通HID键盘/鼠标Host回调就当完成。需要匹配20BC:5128、读取实际配置/端点、实现或复用有线XInput Host处理。
6. 本项目SDK/TinyUSB版本锁定，新增Host依赖时核对API和PIO时钟要求；不要随意整体升级SDK破坏现有Device端。
7. 如果引入第二核心处理PIO Host，必须重新审查Flash安全擦写的跨核协调；原版第二核心没有启动，原有安全假设会改变。
8. 保持单个PC游戏控制器，不额外再输出一只HID游戏手柄。键盘/CDC是否保留可以沿用现状。

## 6. 主要代码入口

| 文件 | 职责/下一阶段关注点 |
|---|---|
| `firmware/main.c` | 当前单核主循环，ADC/按钮/CDC调度 |
| `firmware/hal.c`、`hal.h` | 两路ADC、GP14按键；踏板接线不因桥接而改变 |
| `src/core/pedal.c`、`include/pedal.h` | 滤波、校准、死区、曲线和逻辑模式 |
| `src/core/xinput_protocol.c` | 20字节报文、原生USB配置、OS字符串和XUSB10兼容描述符；目前只填LT/RT，按钮/摇杆为0；新增`xinput_axis_quantize()` |
| `src/core/xinput_pad.c`、`include/xinput_pad.h` | 新增：严格解析Xbox360有线20字节Host报告；短包/错误报告ID拒绝；中立谓词 |
| `src/core/bridge.c`、`include/bridge.h` | 新增：Host状态机、超时/重连、OVERRIDE/MAX合并、20字节输出；尚未被`usb.c`调用 |
| `tests/test_xinput_pad.c`、`tests/test_bridge.c` | 新增11项CTest，覆盖解析、回中、握手、超时、断连、OVERRIDE/MAX |
| `firmware/xinput_device.c` | TinyUSB自定义Device类、IN81/OUT01、能力/LED/GET_REPORT、稳定SRAM缓冲；不是Host驱动 |
| `firmware/usb.c` | 原生与旧HID分支、报告调度、中立屏障、键盘实例0映射到逻辑gate1 |
| `src/core/report_gate.c` | 模式/配置变化时等待手柄与键盘中立完成；注意XInput包头byte1=20不能当非中立输入 |
| `firmware/storage.c` | 双槽保存与SDK flash_safe_execute，配置区从0x101FE000开始 |
| `src/core/config_record.c` | 40字节版本化小端记录、CRC/序号；保持用户校准兼容 |
| `src/core/console.c` | GET/SET/CAL/MODE/SAVE，GET含usb_transport=XINPUT |
| `tools/pedal_gui.py`、`pedalctl.py` | 串口调参；完整ERR为CommandRejected，保持连接，真正通信失败才断开 |
| `tools/check_xinput.py` | 只读调用系统XInputGetState，无映射/模拟/按键注入 |

## 7. 构建、测试和产物

环境：Windows PowerShell，Python3.11，CMake、Ninja、Visual Studio Build Tools的Clang/LLD。**Git仓库已建立**（`main`分支，基线`6fa0512`）；按阶段提交，不要声称没有历史。

```powershell
Set-Location -LiteralPath 'D:\练习项目\RP2350a'
powershell -ExecutionPolicy Bypass -File tools/build_host.ps1
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode xinput
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode hid
powershell -ExecutionPolicy Bypass -File tools/start_gui.ps1
.\.venv\Scripts\python.exe tools/check_xinput.py --seconds 30
```

- 最新测试 **29项C CTest + 19项Python全部通过**。桥接核心日志：`docs/reports/logs/software-bridge-core.txt`；基线日志：`docs/reports/logs/software-baseline-host.txt`。
- 原生固件：`dist/xinput/pedals-xinput.uf2`，已烧录，80,384字节。
- SHA256：`4aca95a4a7f06559d88b5d80a71aa5f64bf3b46e1f6c39ec361deb4843641f70`。
- HID回退：`dist/hid/pedals-hid.uf2`。`dist/pedals.uf2`是更早的HID版本，**不要把它误当当前原生固件**。
- 原生程序结束0x10009CEC；配置区0x101FE000/0x101FF000，末尾8KiB由链接脚本排除。普通UF2更新不应擦掉校准。
- Arm工具链在中文路径下找不到标准库：构建脚本临时将项目SUBST到空闲R:，finally移除；可用`-DriveLetter S`避让。受限沙箱可能禁止SUBST，需要正常本地终端或相应执行权限。
- PC测试用Clang/LLD规避本机MSPDB140.DLL错误；脚本使用完整编译器路径，直接裸调用cmake可能遇到环境问题。
- `deps/`已有Pico SDK2.2.0、TinyUSB锁定提交`86ad6e56c1700e85f1c5678607a762cfe3aa2f47`、Arm GNU14.3.rel1；不需要重新下载几百MB工具链。
- 尚未引入Pico-PIO-USB依赖，也没有XInput Host实现。`deps/xinput-research/`是此前只读参考，不是正式依赖。

只读PnP诊断可筛选`VID_CAFE&PID_4012`与`VID_20BC&PID_5128`，查询Service及CompatibleIds。沙箱内CIM或XInput读取可能被限制，先前在允许的只读本机执行中才成功。不要把沙箱拒绝当设备故障，更不要据此重装驱动。

## 8. 用户操作与残留状态

- 曾误走Steam映射路线，已在用户要求后停止UI操作。**当时启用了FH6的Steam Input；已经多次告知用户自行关闭，但没有确认最终是否关闭。** 不应擅自再操控Steam或把Steam映射当方案。
- 用户已能打开GUI、连接、校准和保存。旧COM7升级到COM8，未来枚举可能继续变化。
- 用户最初无万用表；传感器仅确认5V供电，具体型号/输出电压/厂家线序仍未知。图中红5V/黑地/白黄OUT及每路10k/10k+104电容是条件假设；用户反馈读取正常不能替代电气规格核实。不要重新要求按颜色裸接5V信号到ADC。
- 面包板图：`docs/images/breadboard-dual-pedals.png`；说明`docs/breadboard-wiring.md`。无需为USB合并重新改踏板调理电路。

## 9. 建议的后续阶段与验收

用户明确实施后，按阶段推进并各写报告：

1. 核实R13/Host硬件和接收器供电，确定是否需要用户物理改板；在未确认前不声称接收器可直接插用。
2. 仅接收器Host枚举，记录VID/PID、速度、接口/端点及原始输入，确认摇杆和所有按键。
3. 已完成的纯软件部分：`xinput_pad`解析、`bridge`状态/超时/OVERRIDE/MAX合并、回中容差4000、29项CTest。注意这些模块**尚未接入**`usb.c`，不能据此宣称桥接可用。
4. 连接原生Device端输出，保持现有校准/CDC/Flash协议；复核多核安全与吞吐/延迟。
5. **电脑端只保留开发板一只游戏手柄，接收器插在开发板而非电脑。** 在同一个XInput槽位实测：LX非零同时RT非零、LX非零同时LT非零、双踏板与按钮同时输入。
6. 接收器拔插、无线手柄关机/重连、保存Flash、长时稳定性验证后再验收FH6。
7. 最后考虑震动从PC经板端回传接收器，不把认证透传当完整按键/摇杆透传。

## 10. 资料与历史报告

- [微雪板卡Wiki：含R13 Host热插拔说明](https://www.waveshare.com/wiki/RP2350-USB-A)
- [微雪原理图](https://files.waveshare.com/wiki/RP2350-USB-A/RP2350-USB-A.pdf)
- [Pico-PIO-USB作者项目：支持RP2040/RP2350](https://github.com/sekigon-gonnoc/Pico-PIO-USB)
- [微软MS-XUSBI OS兼容描述符](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-xusbi/601a3107-6583-4e80-867e-118829cb573e)
- [微软20字节XInput报文](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-xusbi/e79d4543-9614-4db7-9321-f018575e30e3)
- [微软XUSB请求](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-xusbi/6e2478bf-d8f0-4e19-a489-7989a34918d1)
- [SDL作者XInput能力查询](https://raw.githubusercontent.com/libsdl-org/SDL/main/src/joystick/hidapi/SDL_hidapi_xbox360.c)
- [GP2040-CE MIT XInput Device参考](https://raw.githubusercontent.com/OpenStickCommunity/GP2040-CE/main/src/drivers/xinput/XInputDriver.cpp)：API版本比本地新，不直接照搬；主机认证透传功能不等于读取并合并手柄输入。
- [历史报告索引](docs/reports/00-handoff.md)。历史“未烧录/测试正常/下一步游戏”等描述是当时状态，**以本文件和原生实机报告为准**。

## 给下一位agent的任务摘要（可直接复制）

> 先阅读本项目根目录HANDOFF.md。当前原生XInput踏板已上板，GP26→RT、GP27→LT；真实北通BTP-KP20的2.4G USB接收器是另一只控制器，FH6出现输入切换。用户拒绝Steam及PC第三方转换，已批准**软件优先**：Git仓库已建，`xinput_pad`/`bridge`纯C解析合并核心及29项CTest已完成，但**尚未接入固件，USB-A Host栈也未实现**。用户明确暂不修改硬件（R13未拆）。下一步是做Host-only探针：vendor Pico-PIO-USB、TinyUSB双rhport、自定义XInput Host类、XUSB10/GIP握手A/B、CDC原始报文；先验证20BC:5128在现有硬件上能否读取。不要重做已验证的Device驱动，不要用电脑映射冒充硬件合并，不要把纯C测试当成桥接/游戏验收。
