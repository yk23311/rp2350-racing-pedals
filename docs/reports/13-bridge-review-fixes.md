# 13：桥接审查修复与交接

日期：2026-10-31（Asia/Shanghai）。用户授权：“帮我修改”，范围为上轮审查中的日志/调参冲突、桥接集成测试缺口、过期文档与固件清单。保留MAX策略及40字节Flash配置；本轮没有烧录、操作Steam、改线或拆焊。

## 结论

完成软件修复、PC回归和两种固件构建。**新固件0.3.1尚未烧录，不能宣称实机或FH6验收通过。** 最初“同时转向+踩踏”的问题已有同报文自动测试，仍需用户上板操作取得Windows和游戏证据。

## 方案与步骤报告

1. 确定根因：Host以异步`[HOST]`行共享CDC，旧客户端只读一行就解析回复，GUI把协议异常作为断连；仅增加重试会让回复归属错位。
2. 先加回归：完整日志穿插GET/SAVE/ERR、GUI保存、日志洪泛、截断日志。运行观察旧代码GET/SAVE因Unexpected response失败，GUI仅执行GET便断开。
3. 客户端修复：只跳过完整已知`[HOST] `行；保留未知行、截断、错误JSON及真正IO错误；日志最多64行，4秒响应接受期限，迟到回复也拒绝。单次底层串口读取最多还会阻塞2秒，不能将其描述为严格4秒返回。
4. 固件修复：`PEDAL_HOST_DIAGNOSTICS`默认OFF，普通版不输出Host日志。用`-HostDiagnostics`构建独立`dist/host-debug`诊断版，不覆盖普通版。设备名更新为RP2350 XInput Bridge，固件版本0.3.1。
5. 补真实集成回归：新增`test_bridge_usb`，以`PEDAL_USB_HOST=1`编译真实`firmware/usb.c`，使用真实桥接核心，模拟硬件USB传输与Host快照来源。原来的无HOST USB测试继续保留。
6. 先观察SAVE测试失败：上一份中立已ACK后，Host收到新按钮或RT/LT，下一USB帧未发送时，旧quiet检查仍允许SAVE。修复为同时检查最新合并按钮/扳机与上一完成帧中立状态，保持摇杆漂移可保存及busy/屏障约束。
7. 构建追踪：增加`tools/write_manifest.py`，每次成功构建自动生成实际文件大小、SHA256、源码HEAD/dirty标记、链接结束点和配置边界。每次构建都设未烧录/未实机验证，不继承旧报告的通过结论。
8. 重写HANDOFF、更新README/报告索引/桥接使用说明/CDC协议。区分普通版、诊断版、独立踏板回退版以及历史探针。

## 验证证据

| 项目 | 本次结果 |
|---|---|
| PC CTest | 36/36通过，含新增6项Host USB集成 |
| Python | 24/24通过，含新增5项客户端/GUI回归 |
| Host普通固件 | 构建、UF2打包成功；二进制没有Host pad日志格式串 |
| Host诊断固件 | 独立构建、UF2打包成功；二进制包含Host pad日志格式串 |
| Manifest | 两种产物的bin/elf/map/uf2大小和SHA256逐一核对成功 |
| 配置区 | 两版本链接结束点均小于0x101FE000，40字节配置格式未改 |
| 差异检查 | `git diff --check`无空白错误（Git另有LF/CRLF提示） |
| 新二进制烧录、游戏 | 未执行 |

日志：[PC测试](logs/bridge-fix-tests.txt)、[普通固件](logs/bridge-fix-firmware.txt)、[诊断固件](logs/bridge-fix-debug-build.txt)。

普通版：`dist/host/pedals-host.uf2`，139264字节，SHA256：

```text
45c6e3074e20f0fa672b5da96bb3d6cf1e6cfe201cf61ad6220bd58c7f0a6b57
```

链接结束：`0x10010f60`。诊断版141312字节，链接结束`0x100113d8`；具体哈希见`dist/host-debug/manifest.json`。两个manifest均标记`flashed=false`、`board_tested=false`；源码工作区含本次未提交修改，`source_dirty=true`。

## 测试覆盖与边界

新增Host集成验证同一份20字节报文同时包含四个摇杆、按钮、油门和刹车，且正确保留MAX；测试中固定ADC样本，避免把真实手柄扳机误当踏板输入。另验证键盘中立ACK未完成不透传、断连/超时全中立、重连必须回中与踏板释放、漂移不阻塞SAVE，以及最新按钮/RT/LT尚未发给PC时也拒绝SAVE。

这些是PC上的真实核心/USB调度代码测试，**没有模拟PIO时序、实际接收器无线关机行为、Flash擦写期间的Host停顿或Windows游戏选择设备行为**。它们不能替代硬件验收。

诊断版异步日志仍可能与长命令回复发生字节层交错；客户端兼容完整日志不意味着能修复交错损坏的数据，日常调参必须用默认无日志普通版。未知/截断内容继续报错，以免错误回复被视为保存成功。

## 交接与下一步

1. 使用[桥接说明](../host-probe.md)烧录普通版；Type-C接电脑、2.4G接收器插开发板USB-A。普通更新应保留校准，不要整片擦除。
2. 松开踏板、扳机及按钮、摇杆回中。双击GUI连接实际COM号，检查持续读取/应用参数/校准/释放后SAVE和重启后保留。
3. 保持转向同时踩油门数秒，再转向+刹车；用只读`tools/check_xinput.py`记录同一槽位LX与RT/LT同时非零，并检查按键+双踏板。当前旧日志没有这项同时输入的充分证据。
4. 检查接收器热插拔、无线手柄关机/回连、Flash保存后Host恢复、至少1h运行及FH6驾驶。R13/15k下拉和总电流预算状态仍待确认，本次没有改硬件。
5. 原独立踏板`dist/xinput/pedals-xinput.uf2`本次未覆盖，可作为功能回退。新普通固件无Host日志，不能因串口不刷诊断行而认定Host未工作。

最新入口：[HANDOFF.md](../../HANDOFF.md)。不使用PC映射器，不擅自恢复Steam Input路线。
