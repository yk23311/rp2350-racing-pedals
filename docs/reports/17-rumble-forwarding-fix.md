# 17：手柄震动回传修复与交接

日期：2026-11-05（Asia/Shanghai）。用户反馈“手柄震动没有了”。

## 根因与结论

0.4.0桥接只处理手柄输入，没有完成游戏输出方向：`xinput_control_response`电机能力为0，`xinput_device.c`只消费LED、丢弃震动包，`host.c`虽然打开了接收器OUT端点却从未提交震动传输。这足以解释接入桥接后失去震动。

现已补齐普通双马达XInput回传，构建0.4.1-rumble-bridge。**软件测试与构建通过，尚未烧录，也没有取得这只20BC:5128接收器的实际震感证据。** 需要用户升级固件后验证，不能把USB模拟测试当实际马达通过。

## 步骤报告

1. 按systematic-debugging核对Device能力、OUT/SET_REPORT消费、Host端点与发送调用；确认数据链路缺失。
2. 对照SDL Xbox360驱动与微软XUSB Set_Report说明，核实标准8字节格式`00 08 00 left right 00 00 00`及8字节能力回复中电机位于offset3/4。
3. 先加Device OUT和SET_REPORT测试，观察旧驱动收到正确包后回调次数仍为0；实现校验与应用层输出hook后通过。
4. 仅Host桥接构建宣告两个电机分辨率255/255；独立踏板构建仍不声称具备实体马达。
5. 新增真实`host.c`+模拟HCD测试，验证从描述符读取的实际OUT端点（测试刻意使用0x02而非硬编码0x01）、固定SRAM缓冲、最新强度合并、零强度停止、失败重试。
6. 应用层将Device输出转给Host，PC USB掉线/挂起、模式/校准/配置重新使能、Host超时/重新初始化都清理旧请求；恢复不自动重放旧强度。
7. 独立审查发现持续NAK可能令旧OUT无限在途、持续PC更新可能重置失败预算。先复现失败，再补停止优先、100ms在途期限、TinyUSB abort及跨轮排空旧completion，失败计数/20ms退避不再随新命令清零。
8. 失败三次转停止，停止再失败三次进入faulted，拒绝非零直到停止成功或接收器重新初始化。新的显式零命令可在保留退避条件下尝试恢复。
9. 新增只读`RUMBLE`诊断命令及CLI `rumble-status`，不自行触发马达；版本更新至0.4.1，PDL2配置格式/Flash位置/GUI配置接口保持兼容。

## 验证结果

- **52/52 CTest、61/61 Python通过**：[日志](logs/rumble-fix-tests.txt)。
- Device测试覆盖OUT与SET_REPORT、畸形/短包/传输失败过滤、LED保留、Host与非Host电机能力分支。
- 7项Host测试覆盖异步缓冲不改写、最新命令、停止/恢复、失败重试、持续busy中止、命令洪泛退避、停止优先、失败耗尽。
- USB应用层测试覆盖回调接入、模式变更禁震、诊断回复；既有曲线、映射、保存与GUI/Session回归继续通过。
- 普通与诊断版构建成功：[普通](logs/rumble-fix-build.txt)、[诊断](logs/rumble-fix-debug-build.txt)。清单文件逐项核对哈希/大小，链接结束均小于配置区0x101FE000。
- 新固件未烧录；GitHub现有v0.4.0 Release未替换，本次源码改动尚未提交/推送，也没有新建Release。

## 产物与使用

日常修复固件：`dist/rumble-fix/pedals-bridge-v0.4.1.uf2`，155136字节。

```text
SHA256 225d25d73620a2883046a08e1443ca739e74784bc3632333c494eb60ae59ffc5
```

诊断版：`dist/rumble-fix/pedals-bridge-debug-v0.4.1.uf2`。此目录附两版本manifest及SHA256SUMS。普通构建原路径`dist/host/pedals-host.uf2`也已更新为0.4.1。

1. 关闭游戏和GUI，通过BOOTSEL复制普通修复UF2；正常更新无需擦Flash，沿用现有校准/曲线/映射。
2. 重新连接Type-C，接收器仍插开发板USB-A；释放踏板、手柄按钮/扳机、摇杆回中。
3. 重新打开游戏，避免沿用旧的“无电机”能力缓存，检查游戏震动选项后验证震感。
4. 若仍不震，关闭GUI释放串口，用实际COM号读取：

```powershell
.\.venv\Scripts\python.exe tools/pedalctl.py --port COM8 rumble-status
```

此命令只读，不测试马达。`received`是PC有效震动包计数；`sent`是接收器USB OUT成功完成计数（包含停止包），不是无线ACK或实际震感证明；`left/right`是当前请求强度，`enabled`表示应用层允许，`available`表示已配置OUT通道，`errors/faulted/pending/in_flight`用于定位链路状态。比较游戏触发前后的计数；若`received`不增长，应先核查游戏/驱动是否发包。若增长而sent不增长，检查Host OUT与错误状态；若两者增长仍无震感，需要实机核对接收器初始化/输出协议。

## 后续交接

先验证实际手柄低频/高频震动与停止，再检查切模式、挂起、拔插和无线重连不会继承旧强度，最后重验转向+踏板。当前仅实现普通双马达震动，没有扳机独立震动、灯效透传或踏板触觉马达。

源码入口：`firmware/xinput_device.c`（校验/能力）、`firmware/usb.c`（应用路由/禁用）、`firmware/host.c`（优先队列、稳定缓冲、重试、中止）。设备端8字节强度包与停止包不修改踏板数据。

参考：[SDL标准Xbox360震动与能力实现](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_xbox360.c)、[微软Set_Report](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-xusbi/a8073349-fa5f-4c7a-9192-6fe393686d4b)。中止行为按本地固定TinyUSB0.18与Pico-PIO-USB0.7.2源码核对。
