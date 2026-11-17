# 0.6.0 原生方向盘与踏板映射交接

## 实施与检验

| 阶段 | 结果 |
| --- | --- |
| 踏板角色 | J1/GP26、J2/GP27 保留各自校准和响应参数。`PEDALMAP 0` 选择 J1 油门，`PEDALMAP 1` 选择 J2 油门。XInput 与方向盘输出使用相同角色。 |
| 方向盘信号 | 左摇杆横轴转向、RT 合并油门、LT 合并刹车。方向盘报告 8 字节，包含有符号转向及无符号油门、刹车，三个轴各 16 位，另有 14 个按钮位和 2 个填充位。 |
| USB 与 GUI | `USBMODE WHEEL`／`USBMODE XINPUT` 先通过 CDC 应答，释放输入后从原 USB 设备断开约 300 ms。USB-A Host 继续服务接收器。GUI 通过同一序列号和目标 PID 重连。Xbox PID 4012，方向盘 PID 4013，同用开发 VID CAFE。 |
| Flash 兼容 | PDL2 原长度和双槽规则不变。字节 84、85 保存油门口及 USB 类型。旧记录的 FF 等同默认值，J1 油门和 Xbox 手柄。只有执行 SAVE 才持久化。 |
| 回归测试 | 60 项 C 测试、132 项 Python 测试通过。Flash 往返测试改为比较序列化字段，避免比较 C 结构体的填充字节，修正后连续重复 30 次通过。 |
| 编译与 UF2 | 普通 Host、诊断 Host、独立 XInput、独立 HID 均编译通过。用 GUI 升级器校验四份 UF2，地址和 SHA-256 均正确。 |

## 提交给实板验收

普通版使用 `dist/host/pedals-host.uf2`。GUI 显示 0.6.0，构建标识为 `0.6.0-wheel`。

普通版 SHA-256 为 `969a902a6e1d201a1f8a70e67a6471d6a403a64e8ae2972163cab8f6471e6b39`。文件覆盖范围是 `0x10000000` 至 `0x10014500`（结束地址不含），配置区从 `0x101FE000` 开始。

1. 选择“固件升级”并刷入普通版 UF2。接收器接开发板 USB-A，电脑连接 Type-C。
2. 在“踏板调校”互换 J1/J2，应用后分别踩 J1、J2 确认刹车和油门，待回零后保存。
3. 切换为 USB 方向盘，等待同板串口重连。在 `joy.cpl` 验证转向、油门、刹车，并同时操作。验证按钮和断连回零。
4. 在 Steam 版《地平线 6》尝试绑定独立三轴。需要时切回 Xbox 模式，验证同时转向与踩踏、游戏震动和重启保留设置。

## 2026-11-16 实板检查

Windows 已枚举方向盘模式 `CAFE:4013`，串口为 COM9。Windows HID 报告有独立的 Steering、Accelerator 和 Brake。DirectInput 可打开 `RP2350 Racing Wheel`，类型为双踏板驾驶控制器，报告 3 个轴和 14 个按钮。

《地平线 6》自定义方向盘配置文件 1 已捕获设备 1 的三个轴，加速为轴 1，刹车为轴 2，转向为轴 3。手动补绑后仍出现“丢失键位绑定”。

曾在游戏原包的通用 Raw Game Controller 模板中加入 `CAFE:4013` 的三轴及菜单、行驶键位。安装后首次启动显示 FHE01，随后撤回预设。游戏目录中的 `inputmappingprofiles.zip` 已恢复为备份原件，并核对 SHA-256 一致。失败预设移为 `dist/fh6-rp2350/inputmappingprofiles.failed.zip`，原件备份为 `dist/fh6-rp2350/inputmappingprofiles.stock.zip`。恢复后游戏启动和自定义布局保存待实机确认。

恢复时退出游戏，把原包备份复制到游戏 `media` 目录并命名为 `inputmappingprofiles.zip`。方向盘模式提供输入，游戏震动转发在 Xbox 模式使用。
