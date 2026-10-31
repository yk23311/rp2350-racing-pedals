# 原生XInput双扳机设计

用户明确要求：设备直接识别为手柄，GP26油门为RT、GP27刹车为LT，不经过Steam Input或电脑映射程序。此要求替换旧的“通用HID双轴用于游戏”路线。

## 选型与边界

采用原生USB XUSB1.0有线手柄协议，由Windows自带xusb22驱动绑定；不采用Steam Input或虚拟手柄转换。整套替换成其他控制器固件会丢失已有校准/Flash/CDC，故只扩展当前TinyUSB设备类驱动。

官方MS-XUSBI协议和本机`C:/Windows/INF/xusb22.inf`均确认有线兼容ID为XUSB10（XUSB20为无线）。复用Pico SDK及TinyUSB端点API；协议实现依据微软公开规范，参考GP2040-CE的MIT实现进行交叉核对，不引入Xbox主机认证。

## USB与报文

- 原生XInput接口0：FF/5D/01，扩展描述符0x21，IN81/OUT01，端点32字节、输入报文20字节。
- 手柄报文LT位于offset4、RT位于offset5，各为0–255。油门16位结果量化到RT，刹车量化到LT；按钮和四根摇杆轴保持0，两扳机可以同时满量程。
- 校准、未使能、键盘模式和USB中立屏障期间，扳机均上报0；键盘作为独立HID接口1保留，CDC继续使用接口2/3。
- 使用新开发PID CAFE:4012，避免旧HID缓存。制造商仍为DIY Pedals，不复制微软厂商名称或VID。
- 提供0xEE微软OS字符串与40字节Extended Compatible ID（只标识接口0为XUSB10）；使用Windows内置驱动，不要求第三方INF或映射软件。
- 控制请求需覆盖PC驱动查询的能力、震动能力、LED状态；不声明实际不存在的马达/按键能力，吞掉OUT端点LED/震动命令，不驱动负载。

## 保留与验证

现有ADC、校准、滤波、曲线及40字节Flash记录不变，末尾8KiB继续保留。保留旧HID构建作为回退，新产物单独放入`dist/xinput/`。游戏运行不依赖CDC工具。

主机测试检查报文、左右映射、量化单调性、同时踩踏、异常/校准中立、USB与OS描述符、控制请求和端点生命周期。交叉构建后检查UF2与Flash区域；上板后必须读PnP的xusb22服务和XInputGetState的独立bLeftTrigger/bRightTrigger。joy.cpl可能将扳机合并显示，不能以该显示判定XInput报文是否独立。

当前仅授权固件实施，用户此前中止了Steam操作，不再操作Steam界面。前次已启用的Steam Input需在原生验收时由用户关闭。
