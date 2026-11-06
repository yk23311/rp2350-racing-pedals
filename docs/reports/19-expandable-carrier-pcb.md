# 19：可扩展接线底板 V0.1：步骤与交接报告

2026-11-06。用户已确认方案，后补充暂定直驱电机 MiGE 90ST-M02430；驱动器未选。**底板原理图、PCB布局布线和样板制造资料已完成；原生ERC/DRC及原理图一致性通过，尚未制造或上电验证。** 本次交付仅为低压接线/扩展底板，不含伺服功率级、驱动器接口子板或直驱固件。

## 步骤报告

1. 核对并保存微雪官方模块原理图、引脚和尺寸图。模块33×17.5mm，两列孔距15.24mm、纵向2.54mm；GP14未引出，底板模式预留GP10，踏板GP26/27不变。
2. 本地提取并验证官方签名 KiCad10.0.8，未系统安装。已验证pcbnew建板、标准库、原理图/PCB导出和3D引擎。
3. 原理图含72个器件、47个命名网络；四路模拟输入、16路I²C按键、I²C屏幕/编码器、I²C PWM控制与SPI接口子板槽。原生ERC0errors/0warnings；6项连接/原生网表等价测试与3项机械测试通过。
4. PCB布局100×80mm、两层、4个M3孔，18孔插接模块；USB接收器组件净空、端子开口方向和丝印已检查。保存布线前原生DRC：0物理违规/0原理图不一致、170处未连接，作为布线前后证据。
5. 加入M3螺钉头双面铜箔禁布区域；原始DSN完整保留实际铜箔/安装孔约束。使用官方Freerouting2.1.0 JAR和系统已有Java21离线布线，导回KiCad并铺双面地。未删除实际约束来绕过工具错误。
6. 完成581段走线、27个过孔，72个器件/238焊盘。PCB共11个区域：8个真实螺钉铜箔禁布区、1个接收器元件禁放区、2个地铺铜。原生KiCad最终DRC为0违规/0未连接/0封装一致性错误。
7. 导出9层Gerber、Gerber Job、独立PTH/NPTH钻孔、两张钻孔图；原理图PDF、5页1:1黑白PCB PDF、板图SVG和完整3D预览已导出并目视检查。钻孔107个PTH（含27过孔）及4个3.2mm NPTH，坐标/外形已复核。
8. 独立审查核对实际PCB全部器件/焊盘网络与模型，结果无差异；模块官方孔位/方向、IC引脚/地址、默认关断、连接器丝印和制造文件未发现阻碍工程样板交付的确定性缺陷。完整Python回归118项通过，其中9项为新增电气/网表/机械测试。

## 文件与交付入口

- [工程说明与接线表](../../hardware/carrier/README.md)
- [电机资料与接口限制](../../hardware/carrier/motor-notes.md)
- [电路计算、器件资料和功耗边界](../../hardware/carrier/circuit-notes.md)
- `hardware/carrier/carrier.kicad_pro` / `.kicad_sch` / `.kicad_pcb`
- `hardware/carrier/reports/erc.rpt`、`carrier-netlist.xml`、`carrier-unrouted.dsn`
- `tools/hardware/build_schematic.py`、`build_pcb.py`、`board_geometry.py`
- `tools/hardware/export_carrier.ps1`：默认检查/导出当前板图，`-Rebuild`复现布局并导入保留SES，`-Route`重新布线。ERC/DRC均是制造导出门禁。
- `dist/carrier-v0.1/carrier-v0.1-project.zip`：可编辑工程、BOM、预览、报告及重建脚本。
- `dist/carrier-v0.1/carrier-v0.1-fabrication.zip`：样板Gerber/钻孔包；本次没有代下单。
- `hardware/carrier/manifest.json` / `SHA256SUMS.txt`：实际文件摘要；发行目录另有ZIP摘要。

## 验证证据

| 检查 | 实际结果 | 文件 |
|---|---|---|
| KiCad10.0.8原理图ERC | 0错误、0警告，退出0 | `reports/erc.rpt` / `erc.json` |
| KiCad10.0.8 PCB DRC+parity | 0违规、0未连接、0封装错误，退出0 | `reports/drc.rpt` / `drc.json` |
| 原生PCB计数 | 72器件、238焊盘、581走线段、27过孔 | `reports/pcb-summary.json` |
| 原始网表与设计规范 | 全部元件、值、封装、针号/网络一致 | `reports/carrier-netlist.xml`；Python测试 |
| Python完整回归 | 118项通过 | `reports/python-tests.txt` |
| 制造钻孔 | 107PTH、4NPTH，无盲/埋孔 | `reports/drill.rpt` |

ERC/DRC覆盖的是其已配置规则，不证明实际传感器兼容性、噪声、EMC、功耗、长期可靠性或机械机壳尺寸。3D模块高度/USB外壳为代理几何，不能当精确机壳依据。工具来源/签名、12个官方标准器件STEP和布线路由来源见 `hardware/reference/cad-toolchain.md` 与PCB摘要。

## 交接报告：下一阶段

1. 复核BOM与本次加工包后制作少量样板，按照底板README的顺序装配；JP1先保持开路。不把现有工程文件当已完成实物验收。
2. 首次不接外设，先检查短路/电源及模块插接方向，再逐路验证原有双踏板与USB手柄桥接；重新核对校准端点和整机USB电流。
3. 扩展16键、第三踏板、面板编码器、I²C屏幕和PWM需要后续HAL/逻辑/GUI适配；先按原厂资料验证输入/默认输出，再开放软件控制。
4. MiGE90ST-M02430参考目录给额定2.4N·m、峰值7.1N·m，不能把峰值当持续扭矩。确认实物铭牌/编码器版本和配套驱动器完整型号，再定扭矩指令、反馈、隔离、硬件急停与再生能量处理。
5. 选定驱动器后设计J11对应接口子板及真正方向盘力反馈固件。当前J7不是伺服编码器口，J11不是伺服驱动器CN1/CN2，EN不是STO，不得直连电机动力或5V差分编码器。

现有0.5.0固件/GUI未修改；仅原双踏板和手柄桥接继续兼容，新第三踏板/I²C按键/编码器/PWM/直驱需要后续适配。J7不接MiGE的5V差分电机编码器，J11只是3.3V板内SPI子板槽，EN不是STO，底板不承载电机功率。现有USB描述符整机100mA预算仍须实测核算。

源文件保存在本地`codex/expandable-carrier`；没有推送GitHub、更新Release、烧录开发板或制造下单。公开v0.4.0附件与本次硬件工程无关。
