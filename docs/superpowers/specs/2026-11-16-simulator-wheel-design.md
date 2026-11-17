# RP2350 原生 USB 方向盘与踏板映射

经用户确认，USB Host 继续读 2.4G 接收器。PC 端可在 Xbox 手柄和原生 HID 方向盘间切换，切换时 USB 重新枚举，GUI 按板子序列号重连。方向盘以 Generic Desktop Joystick 作为顶层集合，三个轴使用 USB HID Simulation Controls 的 Steering、Accelerator 和 Brake。左摇杆横轴提供转向，油门和刹车为独立 16 位轴，各自与 RT、LT 取较大值，现有游戏手柄按键映射转为方向盘按钮。现有键盘映射、Xbox 震动转发和串口升级继续支持。

J1/GP26 和 J2/GP27 独立保存端点、死区、曲线和滤波。GUI 可互换两口角色，映射在处理完物理轴后生效。方向盘模式和踏板映射按现有流程应用到 RAM，再由用户选择保存到 Flash。旧配置默认保持 Xbox 模式与 J1 油门。模式切换先回复串口命令并释放输入，再重新连接 USB。

验收分为本地测试、Windows 枚举和游戏绑定。方向盘首版提供输入轴和按钮。《地平线 6》的实际绑定与硬件验收需实机确认。

[USB-IF HID Usage Tables](https://www.usb.org/sites/default/files/hut1_21_0.pdf)
[Microsoft 的 HID 游戏设备枚举说明](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/hidclass-hardware-ids-for-top-level-collections#special-purpose-hardware-id)
[Forza Horizon 6 支持的方向盘](https://support.forza.net/hc/en-us/articles/51674028831251-FH6-Supported-Wheels-and-Devices)
