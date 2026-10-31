# 10 原生XInput：步骤与交接

日期：2026-10-31。用户明确要求USB设备直接作为手柄，GP26为RT、GP27为LT，排除Steam Input及主机转换软件。

## 步骤报告

1. 停止此前Steam映射操作，告知用户此前已启用游戏Steam Input，该开关需在原生游戏验收时由用户关闭；此后未再操作Steam。
2. 使用微软公开MS-XUSBI、本机xusb22.inf及开源作者实现交叉核查；采用XUSB10有线兼容ID，开发PID从4011更换为4012，未复制微软VID。
3. 先写失败测试，再实现20字节原生报文、独立RT/LT、OS字符串/兼容描述符、能力查询与TinyUSB自定义设备类。保留独立键盘HID和CDC。
4. 补充实际`firmware/usb.c`的模拟集成测试，验证键盘HID实例0对应逻辑屏障1、XInput长度头不误判为非中立、两种中立ACK完成后恢复、USB传输失败及挂起回零使能。
5. 独立审查发现LED状态GET_REPORT缺口：先补失败测试，再加入OUT及控制SET_REPORT两条路径缓存LED模式、GET_REPORT查询，未驱动物理LED或马达。
6. 最终主机验证：18/18 CTest、19/19 Python通过；XInput和HID回退均交叉构建成功。日志见`logs/native-xinput-host.txt`、`logs/native-xinput-build.txt`、`logs/hid-fallback-build.txt`。
7. 新固件UF2共157块、80,384字节，重建BIN一致；程序结束`0x10009CEC`，低于配置区`0x101FE000`，Flash擦写函数在SRAM。见`logs/native-xinput-artifacts.txt`和`dist/xinput/manifest.json`。

## 实机进展

用户已反馈“已烧录”。只读查询确认CAFE:4012接口0显示“支持 Windows 的 XBOX 360 手柄”，Status OK / CM_PROB_NONE，服务为`xusb22`，Compatible ID包含`USB\MS_COMP_XUSB10`；键盘和CDC也正常，新串口COM8。

独立进程直接调用系统`xinput1_4.dll`的`XInputGetState`返回槽位0，LT=0、RT=0，按钮和四个摇杆均0。烧录前基线为空列表，烧录后出现原生控制器。本检查不是Steam注入或虚拟手柄工具。

30秒原生API采样已完成，共590个样本，记录见`logs/native-xinput-live.json`：LT最小0/最大255，RT最小0/最大255；观察到全松开、仅RT、仅LT、双路同时255，全部按钮和四个摇杆保持中立。原生独立双扳机实机验证通过。游戏内响应仍需用户验收，不以驱动绑定成功代替实际驾驶测试。

## 交接报告

首选固件：`dist/xinput/pedals-xinput.uf2`。参数格式、引脚和调理电路不变。使用方法见`docs/native-xinput.md`。Windows驱动识别与原生API独立双扳机均已实测通过，游戏内验收尚未完成；本设备为独立控制器，不自动合并另一只实体手柄。
