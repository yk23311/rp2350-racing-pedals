# 原生XInput实施计划

**目标：** 固件直接提供Windows XInput RT/LT，保留校准及CDC，无电脑转换。

- [x] 1. 先写纯C协议和USB布局测试并观察失败；实现20字节报文、XUSB10 OS描述符和PC控制查询。
- [x] 2. 增加TinyUSB自定义设备驱动，连接XInput传输完成回调到既有中立屏障；键盘HID实例调整为0。
- [x] 3. 增加设备驱动模拟测试，覆盖描述符拒绝、端点忙、缓冲复制、OUT重挂载、失败恢复及总线复位。
- [x] 4. 提供HID回退构建与独立XInput产物；交叉构建、UF2/Flash地址核对，运行相关回归测试。
- [x] 5. 提供标准库XInput只读检测工具，用户已烧录；Windows内置xusb22绑定和原生API读取已确认，动态踩踏采样记录与游戏测试分别报告。

实现位置：`include/xinput_protocol.h`、`src/core/xinput_protocol.c`、`firmware/xinput_device.*`、`firmware/usb.c`、`tools/build_firmware.ps1`、`tools/check_xinput.py`与对应测试。USB核心数据处理与板级TinyUSB调用保持分离。无Git仓库，不虚构提交。
