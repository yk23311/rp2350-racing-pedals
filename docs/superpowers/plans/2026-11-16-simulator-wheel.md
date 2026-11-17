# RP2350 原生 USB 方向盘与踏板映射实施计划

用现有 Host 固件作为 USB 入口，用 PDL2 保存新增设置。用现有 CDC 会话与 Qt 设置页提供操作入口。

- [x] 在 tests/test_bridge.c 覆盖物理端口互换、方向盘同帧三轴和中性输出。src/core/bridge.c 将校准后输出路由至油门和刹车，并复用手柄变换。
- [x] 在 tests/test_control_storage.c 覆盖 PDL2 旧记录兼容和新设置恢复。修改 src/core/control_record.c 与 src/core/control_console.c，新增 PEDALMAP 0/1 和 PROFILE 字段。
- [x] 在 tests/test_bridge_usb.c 覆盖切换命令、USB 断开重连和报告投递。更新 src/core/usb_layout.c、firmware/usb.c 和 firmware/main.c。
- [x] 在 tests/test_control_gui.py 和 tests/test_control_session.py 覆盖互换指令及新串口 PID。更新 tools/control_center.py 和 tools/control_session.py。
- [x] 运行 tools/build_host.ps1 和 tools/build_firmware.ps1 -UsbMode host，核验生成的 UF2。更新操作说明与交接报告。
- [ ] 将 0.6.0 烧录实板，在 Windows 检查三个轴和双向 USB 切换，再在《地平线 6》验证游戏绑定。
