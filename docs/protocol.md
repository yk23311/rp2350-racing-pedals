# CDC协议 v1

115200波特率为主机串口设置，USB CDC本身不以UART波特率传输。主机应置DTR。ASCII逐行、LF结束，可接受CRLF；命令最多127字符，不带终止符。每次只发送一条命令并等待完整响应。

| 命令 | 响应/行为 |
|---|---|
| `PING <32位小写十六进制token>` | `OK {"sync":"<token>"}`，建立会话，排除上次连接的残留响应 |
| `GET` | `OK {...}` JSON状态，含protocol/mode/armed/calibration_axis/raw/filtered/output/axes |
| `SET axis on off gamma window` | 校验通过原子更新RAM，清滤波、输出中立，需松开重新使能 |
| `CAL axis BEGIN` | 全松开位置开始专用校准，期间所有输出中立 |
| `CAL axis END` | 踩到底并保持时结束；小于128 counts拒绝，保留原配置，会话可重试或CANCEL |
| `CAL axis CANCEL` | 取消当前对应轴的校准，不更改旧参数 |
| `MODE JOYSTICK` / `MODE KEYBOARD` | 固定枚举不变，切换逻辑；先中立、回零后重新输出 |
| `SAVE` | 仅采样有效、已使能、无校准且双轴中立时尝试持久化；USB中立未完成也会拒绝 |
| `DEFAULTS` | 仅RAM恢复默认未校准配置；校准中拒绝；需SAVE才影响重启 |

成功无数据返回 `OK\n`。错误返回 `ERR COMMAND`、`ERR STATE_OR_VALUE` 或 `ERR TOO_LONG_OR_BINARY` 等。收到错误不能假设发生了参数修改或保存。超长/二进制输入整行丢弃直到LF，下一行正常恢复。

axis：0油门/1刹车；0≤off<on≤5000（万分比），gamma100–400（1.00–4.00），window1–8。端点只经校准产生，防止上位机任意填值导致未验证输出。导出JSON用于审阅和备份，本版不提供端点JSON导入。

正常模式冻结校准；端点大小决定方向。keyboard发W/S，并直接使用行程迟滞状态，避免幂曲线量化改变触发阈值。模式不会写Flash，重启总是JOYSTICK。

板端记录40字节：`PDL1` magic，16位version=1、16位length=40、32位sequence，两个12字节轴配置，末尾32位CRC。全部字段小端；每轴 released/pressed/on/off/gamma 各16位、window与calibrated各8位。CRC为IEEE CRC32，覆盖前36字节。双槽序号比较支持32位回绕；同序号优先槽0。


## 桥接版CDC与SAVE（0.3.1）

普通桥接固件默认不发送Host日志，原有命令格式不变。专用诊断版启用异步`[HOST] `行；客户端兼容跳过完整日志行，最多64行、以4秒为响应接受期限（最后一次串口读取可能额外阻塞至其2秒timeout）。超过期限的回复拒绝；截断或未知内容仍视为通信失步，需要重连。字节层交错不自动修复，日常调参请使用普通版。

桥接SAVE同时检查最近已完成USB帧和最新合并输入的按钮、LT、RT中立；四个摇杆允许漂移。仍需踏板采样有效、armed、未校准、输出为0，且USB中立屏障完成、没有报告传输在途。真实手柄按钮或任一扳机按下时拒绝保存。


## 控制中心0.4.0扩展

主循环统一通过`pedal_usb_feed`完成逐行解析与扩展路由，默认不输出异步日志。所有回复仍在768字节内，命令不超过127字符。

| 命令 | 含义 |
|---|---|
| `CAPS` | control_center/profile/telemetry/bridge能力及版本、persist_format |
| `TELEMETRY` | raw/processed/output三份手柄快照、keys[8]、Host state/age/reports/timeouts、blocked/fresh/keyboard_rollover |
| `PROFILE` | sticks[2]、triggers[2]、bindings[14]当前RAM配置 |
| `STICK i deadzone gamma invert` | i0/1，deadzone0..9500万分比、gamma100..400、invert0无/1X/2Y/3XY |
| `TRIGGER i deadzone gamma` | i0=LT/1=RT，范围同上 |
| `BIND source kind target` | source0..13；kind0目标手柄索引、1键盘HID usage4..E7（E0..E7修饰键）、2禁用target0 |

手柄快照顺序均为`[buttons,LT,RT,LX,LY,RX,RY]`。索引0..13依次为方向上/下/左/右、START、BACK、LS、RS、LB、RB、A、B、X、Y；对应XInput bit0..9及12..15。未知保留位不映射。

曲线和映射在设备上执行，每次使用原始按钮快照，避免级联。手柄曲线之后再与踏板MAX合并。应用新配置时重置输出，需物理输入释放、摇杆回中及USB中立完成；即使来源被禁用也不能在实体键按住时SAVE。

Host桥接构建SAVE现写256字节`PDL2`统一记录，包含踏板和手柄配置；版本2、长度256、序列号、末尾CRC32。地址仍在末尾两个4KiB扇区。启动可读PDL1并在RAM补默认手柄配置，显式SAVE才迁移。旧固件不认识PDL2，降级不保证保留最新校准。非Host构建继续使用PDL1。

键盘报告仍为8字节，最多6普通键+8修饰键；新报告描述符长度64，普通键Usage/Logical范围覆盖0..DF，E0..E7走修饰位。超限发送标准ErrorRollOver，释放后恢复，不会把某个源释放误当全部源释放。


## 0.4.1震动扩展

Host桥接`CAPS`新增`rumble:1`。`RUMBLE`只读返回received/sent/errors、当前请求left/right、pending/in_flight/enabled/available/faulted。此命令不直接启动马达，也不等于硬件验收。CLI：`pedalctl.py --port <COM> rumble-status`。

标准8字节包`00 08 00 left right 00 00 00`经OUT或SET_REPORT进入，严格校验后转发给接收器实际OUT端点。Host构建的C1/01/0000能力回复offset3/4声明255；独立踏板构建保持0。持续busy最长100ms，中止后跨轮排空旧completion再重用缓冲。重试20ms退避，失败3次降停止，停止再失败3次faulted，拒绝非零直到接收器重新初始化或新的显式停止命令成功。停止、挂起、模式/校准变化、Host失联均清理旧强度，恢复不自动重放。

## 0.5.0 测试与升级扩展

仅 Host 构建公布 `CAPS` 的 `rumble_test:1`、`bootsel:1`、`version:"0.5.0"`。

| 命令 | 回复与行为 |
|---|---|
| `RUMBLE TEST left right duration_ms` | `left/right` 为十进制 0..255，时长 100..3000ms，完整语法验证；使能且 Host 可用时 `OK`，否则 `ERR STATE_OR_VALUE` |
| `RUMBLE STOP` | `OK`，取消测试并提交优先停止，即使非零命令已在途也可中止后停震 |
| `RUMBLE` | 原有字段外新增 `testing`、`remaining_ms`；left/right 是当前请求而非无线确认 |
| `BOOTSEL` | `OK {"bootsel":true}`，立即强制手柄/键盘中立与停震，等待 CDC 确认完成后至少 300ms 进入 ROM USB 下载模式 |

测试期间忽略游戏发来的全部震动命令，结束时不回放；之后的新游戏命令正常处理。计时由板端执行，串口中断不延长截止时间。进入升级等待后，后续串口命令收到 `ERR UPDATING`，不修改配置。原始 BOOTSEL 回复未获 CDC 发送确认超过 1.5s 时取消升级等待、重置输出屏障并恢复命令；确认后等待中立/停震最多 1.5s，然后 ROM 重启。300ms 从首次观察到确认完成计时。

GUI 只接受本项目连续 256 字节 payload、family `0xE48BFF59`、从 `0x10000000` 开始且结束不超过 `0x101FE000` 的完整 UF2；不执行擦除命令。软件 BOOTSEL 不等于 COM 口直接写 Flash，数据通过 ROM 下载盘传输。
