# 09 地平线6无法绑定：系统枚举与游戏兼容排查

日期：2026-10-31。状态：Windows识别已确认；游戏绑定未解决。

## 用户反馈

用户确认使用Type-C连接，joy.cpl可以看到设备，但《极限竞速：地平线6》中找不到或不能绑定。不能再以此前“功能正常”的反馈代表游戏兼容验收完成。

## 步骤报告

1. 检查工程中的USB设备、配置、手柄报告描述符及TinyUSB双HID+CDC配置。未在这一步变更固件。
2. 只读查询本机Windows PnP，筛选VID_CAFE&PID_4011。沙箱内CIM查询受限，随后通过授权的只读查询获得设备状态；未安装、卸载或修改驱动。
3. 结果：USB Composite Device、COM7（MI_02）、HID Keyboard Device（MI_01）、HID-compliant game controller（MI_00）均为Status OK / CM_PROB_NONE；两个USB输入设备接口亦正常。
4. 用户进一步确认joy.cpl可见。这些证据支持Windows端复合USB及手柄HID已建立；目前不能将问题归因为USB-C接错或未枚举手柄。
5. 查阅Forza官方FH6支持资料，确认多USB设备需建立自定义方向盘配置，不能承诺DIY双轴设备自动获得预设。Steam版本还提供映射文件DInputIndex/DInputInvertAxis修正方法，但这是轴已匹配后的映射调整，尚不足以作为当前故障的通用修复。

## 交接报告

待确认游戏平台（Steam或Xbox/Microsoft Store）和转向输入方式（键盘、手柄、方向盘及型号）。下一步依此选择游戏自定义配置或进一步输入映射；尚未安装映射软件、修改游戏文件或替换USB设备身份。

官方资料：
- [FH6 Supported Wheels and Devices](https://support.forza.net/hc/en-us/articles/51674028831251-FH6-Supported-Wheels-and-Devices)，重点Multi-USB段落。
- [FH6 Wheel Input on Steam](https://support.forza.net/hc/en-us/articles/51642975681427-Forza-Horizon-6-on-Wheel-Wheel-Input-on-Steam)，用于特定已匹配设备的轴索引/方向修正。

当前验收：Windows设备检测通过；FH6内绑定、轴响应和实际驾驶均仍待验收。
