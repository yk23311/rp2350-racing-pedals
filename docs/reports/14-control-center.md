# 14：驾驶控制中心实施、验证与交接

日期：2026-10-31（Asia/Shanghai）。用户已确认完整GUI重构、手柄曲线/死区、按键映射到手柄或键盘，并回复“开始”。采用[设计](../superpowers/specs/2026-10-31-control-center-design.md)和[实施计划](../superpowers/plans/2026-10-31-control-center-plan.md)。

## 交付结果

新版Qt GUI、板端曲线与映射、遥测与统一配置保存均已实现。默认双击根目录`启动调参GUI.bat`打开新界面。**新0.4.0固件已构建，未烧录、未实机/游戏验收**；界面截图为明确标注的演示数据，不是硬件证据。

## 分阶段步骤报告

| 阶段 | 实施与证据 | 当前状态 |
|---|---|---|
| A 板端纯C处理 | 新增control_profile，左右摇杆径向死区/幂曲线/反向，LT/RT死区/幂曲线，14键快照重映射、目标并集、修饰键及6键rollover；先写测试，再实现 | PC验证通过 |
| B 配置与迁移 | PDL2 256字节统一保存踏板+手柄配置，CRC32/序号、末尾双4KiB；PDL1读入时保留旧校准，显式SAVE才迁移 | 256种断写位置、每字节CRC损坏、序号回绕、Flash安全失败与磨损no-op等模拟测试通过 |
| C 接入与协议 | 手柄处理后再与踏板MAX合并；键盘与手柄共享中立/代际/释放门控；新增CAPS、TELEMETRY、PROFILE/STICK/TRIGGER/BIND | 真实usb.c编译的Host集成通过；CAPS经过实际逐字符feed路径验证 |
| D 桌面GUI | PySide6-Essentials6.8.3 + pyserial3.5，自动识别/重连、20Hz单线程串口工作队列、原始/处理后/最终数据层、仪表/手柄图、曲线游标、编辑/应用/保存状态 | Qt行为、离线/过期、串口模拟及截图检查通过 |
| E 构建交付 | 普通/诊断版分别打包，自动manifest；启动器默认Qt并保留-Legacy；用户说明/报告/HANDOFF更新 | 构建及文件哈希/链接边界检查通过 |
| F 实机验收 | 新固件烧录后同时转向+踏板、键盘释放、保存重启、热插拔、关闭GUI仍有效、FH6驾驶 | 未执行 |

## 审查发现与修复

- 实际CDC解析原本把未知命令返回ERR STATE_OR_VALUE，首次扩展路由只判断ERR COMMAND导致CAPS/TELEMETRY走不到。已统一使用`pedal_usb_feed`并新增真实逐字符命令测试，观察先失败再通过；超长/二进制错误不走扩展兜底。
- 物理来源被禁用不能绕过SAVE；新配置不继承按住的旧键。测试覆盖BIND切目标、模式切换、校准开始/取消、timeout和断连后的键盘释放。
- 原键盘描述符仅声明Usage0..65，与更宽的合法映射不符；现普通键范围0..DF，修饰E0..E7单独位图，描述符长度由63同步到64。范围回归先失败后通过。
- GUI不能跨设备保留旧草稿并误写另一设备；每次新连接清本地基线/未应用编辑和保存标记，等新GET后才允许写。
- 最终Output不能误依赖接收器在线：独立踏板输出仍有效，Raw/Processed继续受Host新鲜度限制。
- 校准端点变化要使Flash保存状态失效；现把完整持久化指纹与可编辑字段基线分开，避免假dirty或假saved。
- 100ms UI watchdog检测500ms无快照，全读数灰显、停止写入、保留草稿，收到新快照后恢复；Host年龄加本地驻留时间，不把旧数据当实时。
- 14个映射来源按新鲜原始输入高亮；多设备显示序列号；合法未知HID usage完整保留，修改其他参数不误写BIND。

## 验证结果

- `tools/build_host.ps1`：**43/43 CTest、61/61 Python通过**，见[完整测试日志](logs/control-center-tests.txt)。Python含22个Qt界面测试、15个串口会话测试及既有回归。
- `start_gui.ps1 -Check`及`-Check -Legacy`均通过；依赖已安装于项目`.venv`。
- 普通与诊断固件构建成功：[普通构建](logs/control-center-build.txt)、[诊断构建](logs/control-center-debug-build.txt)。
- 默认普通固件无异步Host日志，诊断版单独在`dist/host-debug`，不覆盖普通版。
- 所有manifest文件的bin/elf/map/uf2大小与SHA256逐项核对；配置区仍从0x101FE000开始。
- 四页1280×800截图已逐张检查，中文字体正常；踏板和手柄调参主要控件完整显示。900×650时操作栏保留，内容可滚动。

普通固件：`dist/host/pedals-host.uf2`，版本0.4.0-control-center。

- UF2字节数：151040
- SHA256：`2969945a6b14f048f5d8ff5f5a87f7529b0bb3b7a3d64739b8bc346d0532fda2`
- Flash结束：`0x100126b0`，小于配置区0x101FE000。
- manifest标记`flashed=false`、`board_tested=false`、`source_dirty=true`；工作区修改尚未提交。

## UI预览（演示数据）

[概览](../../artifacts/control-center-demo.png)、[踏板](../../artifacts/control-center-pedals.png)、[摇杆/扳机](../../artifacts/control-center-sticks.png)、[映射](../../artifacts/control-center-mapping.png)。这些图仅用于布局验证。

## 使用与交接

详见[一步步使用说明](../control-center.md)。入口`tools/control_center.py`；绘图`control_widgets.py`；串口会话`control_session.py`；旧Tk保留`pedal_gui.py`；启动器`tools/start_gui.ps1`支持`-Demo`和`-Legacy`。

板端：`control_profile.c`变换、`control_record.c`存储记录、`control_console.c`配置命令，`bridge.c`合并，`firmware/usb.c`门控/键盘/遥测，`storage.c`统一持久化。HAL和踏板接线不变。

升级前导出/记录旧校准。烧录新版后旧PDL1会在RAM迁移，直到SAVE才写PDL2。旧固件不认识PDL2，降级不保证最新校准；输出MODE仍只在RAM，重启JOYSTICK，不要把模式当持久化参数。

## 下一步与限制

1. 用户关闭GUI后用BOOTSEL烧录普通UF2，接收器插板USB-A、Type-C接电脑，释放输入回中再连接。
2. 验证原始/处理后/最终显示、同帧转向+两踏板、各类键盘映射与松开、断连/timeout释放、GUI关闭后板端仍执行。
3. SAVE并断电重启核对校准、曲线与映射；检查Flash期间Host恢复、热插拔和长时运行，最后FH6验收。
4. 无无线手柄在线指示协议时，仅显示接收器报告，不根据中立帧虚构无线在线。没有增加震动、鼠标、宏或PC输入注入。
5. 没有改硬件、操作Steam或安装驱动。R13/下拉/总电流实物状态仍待确认；PC模拟Flash与demo不能替代板级验收。

最新交接入口：[HANDOFF.md](../../HANDOFF.md)。
