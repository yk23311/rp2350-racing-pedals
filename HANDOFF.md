# RP2350 驾驶控制中心：接手入口

更新：2026-10-31（Asia/Shanghai），工作目录`D:\练习项目\RP2350a`。**最新版0.4.0-control-center：板端桥接+曲线/映射/配置迁移、Qt可视化GUI已实现并构建；本次新固件尚未烧录或实机验收。** 最新[步骤/交接报告](docs/reports/14-control-center.md)，[一步步使用](docs/control-center.md)。历史探针报告不是当前状态。

## 用户目标与授权

- Steam版《极限竞速：地平线6》真实2.4G手柄转向/按键，GP26油门RT、GP27刹车LT同时工作。
- 禁止Steam Input、电脑虚拟手柄和第三方输入转换。接收器插板USB-A，Type-C接电脑，电脑只接收一只完整原生手柄。
- 用户已明确批准现代GUI：自动串口、踏板百分比/图形、真实手柄状态、踏板及摇杆/扳机曲线/死区、按钮映射到其他手柄按钮或键盘；不做鼠标和宏。
- 参数由板端执行，GUI关闭后仍有效。保持MAX合并、键盘/CDC；每阶段交接和测试记录。
- 本轮只改软件、构建和测试：没有烧录、改线、拆焊、操作Steam或安装驱动。

## 最新软件状态

- Qt桌面入口`tools/control_center.py`，深色中文4页：概览、踏板调校、摇杆与扳机、按键映射。默认双击`启动调参GUI.bat`。
- pyserial工作线程自动识别CAFE:4011/4012串口、单板自动连接、多板选择/序列号展示；20Hz有界轮询、断线同序列号重连、不重放写入。新连接清理旧草稿并重读基线，避免跨设备覆盖。
- 原始/处理后/最终手柄三层快照、摇杆二维/按钮/扳机图形、踏板百分比和ADC、曲线游标/迟滞标记。500ms无快照时读数灰显、禁止写入，保留本地草稿；demo明确标注模拟数据且不访问硬件。
- 编辑/应用RAM/保存Flash分开，只有成功SAVE ACK才显示已保存；校准端点变化使旧saved失效。旧固件无CAPS时降级为仅踏板，不伪造手柄状态。
- 板端`control_profile`：两摇杆径向死区+γ+XY反向、两扳机死区+γ、14数字键按快照映射为手柄/键盘/禁用；多源同目标取并集，普通键最多6个，修饰键独立，rollover可恢复。
- USB-A Host仍GP12 D+/GP13 D−，Pico-PIO-USB0.7.2，单核120MHz；Type-C原生CAFE:4012/XUSB10，Windows内置xusb22。设备保持一只XInput+键盘+CDC。
- 手柄曲线先作用于Host原始快照，再与踏板独立曲线做MAX。Host见过后断开/250ms无报告则完整中立；重连需两帧回中（摇杆容差4000）、踏板释放和USB中立屏障。
- 应用、模式/映射变化、校准、timeout/断连都释放旧键；按住的源键不直接继承到新映射。保存还检查物理源按钮/扳机，即使已禁用也不能绕过。
- 键盘报告64字节描述符覆盖普通Usage0..DF、修饰E0..E7；实际键盘输入报告仍8字节。
- 新增有界CAPS/TELEMETRY/PROFILE/STICK/TRIGGER/BIND；旧GET/SET/CAL/MODE/SAVE保持。主循环经`pedal_usb_feed`路由，回复≤768字节、命令≤127字符。普通版无异步Host日志。

## 保存、升级与回退

- HOST桥接使用**PDL2 256字节统一记录**，踏板与手柄配置一起CRC32/序列号/双槽原子保存；位置仍末尾两4KiB，0x101FE000与0x101FF000。
- 可读取旧PDL1 40字节，保留踏板校准并补默认手柄设置；只有显式SAVE才写新格式。单核Flash安全假设`PICO_FLASH_ASSUME_CORE1_SAFE=1`，若启动core1必须重做锁定协调。
- **旧固件不认识PDL2**：保存新格式后降级可能使用旧校准或默认值。升级前用旧GUI导出/记录校准，不得宣称无损降级。不要整片擦除。
- MODE仅RAM，重启JOYSTICK；曲线/映射/踏板配置可持久化。非Host构建继续PDL1。
- `dist/host/pedals-host.uf2`：新0.4.0普通桥接，尚未烧录。
- `dist/host-debug/pedals-host.uf2`：新0.4.0专用诊断版；日志可能与长回复交错，不作为可靠调参基线。
- `dist/xinput/pedals-xinput.uf2`：旧独立踏板回退，本轮未覆盖；`dist/hid`旧HID。`dist/pedals.uf2`更旧，不要混用。
- 每次构建自动刷新manifest实际SHA/大小、链接边界、源码HEAD/dirty；本次均`flashed=false`、`board_tested=false`。精确SHA见[阶段报告](docs/reports/14-control-center.md)与产物manifest。

## 已验证与仍待验证

- 最新 **43/43 CTest、61/61 Python通过**，其中22个GUI、15个Session测试；见[日志](docs/reports/logs/control-center-tests.txt)。
- 纯C：径向曲线/端点/目标并集/修饰及rollover；Flash模拟覆盖256断写位置、记录每字节CRC、序号回绕、迁移、联合保存、擦写失败、无修改不擦写。
- 真实`usb.c`以HOST编译：同帧四轴+按钮+双踏板、键盘ACK屏障、断连/timeout/重连、按住时BIND/模式/校准释放、物理源SAVE、CAPS逐字符feed与遥测3层。
- Qt与Session：安全扫描/回连/旧固件降级、ACK保存/草稿隔离、迟到与失步、过期数据灰显、未知HID保留、保存指纹、窗口布局。四页1280×800截图与900×650滚动检查通过。
- 新普通/诊断固件均构建成功、所有bin/elf/map/uf2哈希和配置边界已核对；Qt和旧Tk入口Check通过，依赖已在`.venv`。
- **本轮没有硬件输入/Flash/游戏证据**；模拟Flash和演示截图不能代表实机通过。旧实机日志只证明旧版本接收器/各输入曾分别有效，缺同帧转向+踩踏充分证据。
- 早期原生0.2独立踏板已绑定xusb22并实测RT/LT0..255，见[旧报告](docs/reports/10-native-xinput.md)；不能外推到0.4.0。

## 构建与启动

```powershell
Set-Location -LiteralPath 'D:\练习项目\RP2350a'
powershell -ExecutionPolicy Bypass -File tools/build_host.ps1
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode host
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode host -HostDiagnostics
powershell -ExecutionPolicy Bypass -File tools/start_gui.ps1
powershell -ExecutionPolicy Bypass -File tools/start_gui.ps1 -Demo
powershell -ExecutionPolicy Bypass -File tools/start_gui.ps1 -Legacy
```

构建环境已有Pico SDK2.2.0、TinyUSB固定提交86ad6e56、Arm GNU14.3.rel1、PIO-USB0.7.2，不要重下载。PC测试Clang/LLD规避MSVC调试链接错误；Qt测试用项目`.venv`Python。固件临时SUBST空闲R:解决中文路径，受限环境可能拒绝，允许本机执行后成功，脚本finally移除。依赖`tools/requirements.txt`固定pyserial3.5与PySide6-Essentials6.8.3。

## 文件入口

| 文件 | 职责 |
|---|---|
| `tools/control_center.py` / `control_widgets.py` | Qt窗口、配置编辑、仪表/曲线/手柄绘图 |
| `tools/control_session.py` | Qt信号与独占串口线程、能力/配置/遥测读取 |
| `tools/pedal_gui.py` / `pedalctl.py` | 旧Tk和通用串口客户端 |
| `src/core/control_profile.c` / `control_console.c` | 曲线/映射核心与配置命令 |
| `src/core/control_record.c` / `firmware/storage.c` | PDL1迁移、PDL2及双槽 |
| `src/core/bridge.c` / `firmware/usb.c` | 合并与实际USB门控、键盘、遥测 |
| `firmware/host.c` / `main.c` | 接收器驱动/握手与主循环调度 |
| `tools/build_firmware.ps1` / `write_manifest.py` | 构建/诊断隔离及清单 |
| `tests/test_control_*.c` / `.py` / `test_bridge_usb.c` | 本轮主要回归 |
| `artifacts/control-center-*.png` | 明确标为演示数据的界面截图 |

## 下一位执行者的实机任务

1. 按[使用说明](docs/control-center.md)备份旧校准并由用户烧录普通0.4.0；接收器插板USB-A，Type-C接电脑，原踏板线不变，释放所有输入。
2. 新GUI自动识别实际端口（不能假设永远COM8），查看3层数据、调参、校准、SAVE并重启核对；GUI关闭后映射应继续由板端执行。
3. 同一XInput槽位实测`LX!=0 && RT>0`、`LX!=0 && LT>0`，以及按键/键盘+双踏板。验证重复目标、修饰键、按住时改映射不粘键。
4. 接收器拔插、无线手柄开关、Flash保存期间Host恢复、至少1h运行与FH6驾驶。无线关机但接收器发中立帧时只能显示接收器有数据，不能伪称无线在线。
5. 用户自行确认Steam Input关闭；先前曾被启用，最终状态未知，不擅自再操作Steam或走PC映射。

## 实物与历史注意

微雪官方说明Host热插拔需移除R13，实物R13/R10/15k下拉及总电流状态没有本轮确认；本轮没有改硬件。用户无万用表，传感器只知道5V供电，原10k/10k分压+100nF图是假定模拟OUT，不要让未知5V直入ADC。踏板图与说明仍在docs/images及docs/breadboard-wiring.md。

Git已有基线6fa0512、桥接8f7c0a2、MAX7539a07；本轮及上轮改动已统一提交并推送公开仓库yk23311/rp2350-racing-pedals；源码提交9b81c3f，后续文档提交以git log为准，见docs/reports/15-github-publication.md。固件manifest记录的是构建当时的HEAD/dirty状态，不冒充当时已提交。历史报告见[总索引](docs/reports/00-handoff.md)，本文件优先。
