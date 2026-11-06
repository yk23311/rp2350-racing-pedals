# 可扩展接线底板 V0.1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付既有 RP2350-USB-A 的可编辑底板原理图、已检查的 PCB 工程及样板制造资料，方便踏板接线并预留直驱伺服接口子板。

**Architecture:** 官方模块原封装插接，USB 留在模块；四路模拟输入、I²C GPIO/PWM 扩展和低压扩展槽组成底板。使用真实 KiCad 完成 ERC/DRC、网表一致性和制造文件导出；伺服功率和未知协议不在底板上实现。

**Tech Stack:** KiCad 10.x、Python、官方 KiCad 器件库；必要时复用 Freerouting 完成低压双层板走线，再由 KiCad 验证。

## Global Constraints

- 用户已确认 docs/superpowers/specs/2026-11-06-expandable-carrier-design.md 的范围，继续实施不再逐步索要确认。
- 模块 33×17.5mm；排距15.24mm，纵向2.54mm，首孔Y=2.88mm；按官方右GP0..8、左VSYS/GND/3V3/GP29/28/27/26/10/9，禁止套Pico封装。
- GP26油门、GP27刹车兼容；GP28第三踏板、GP29辅助；GP0/1 I²C；GP2/3编码器；GP4/5/6/7 SPI；GP8使能、GP9中断/故障；GP10模式键预留。
- GP12/13 USB、GP16 RGB不能分配给底板；GP14未引出，不改现有固件来伪称新按键已支持。
- 16路按键使用I²C扩展器；两路震动控制使用I²C PWM扩展器和外部驱动。数字逻辑3.3V，传感器5V独立丝印；不承载电机功率。
- 不生成未选型伺服的功率/母线/STO电路；普通GPIO EN不宣称安全认证急停。
- 板外形不超过100×80mm，2层、1.6mm、4个M3孔；以工程样板交付，未经实物验证不称量产设计。不上传GitHub/下单制造。

### Task 1: CAD 引擎和机械资料

**Files:** deps/kicad/（忽略的本地工具）；hardware/reference/ 资料与来源记录。

- [ ] 从KiCad官网指向的发布下载Windows安装包，验证官方数字签名，仅提取到项目deps目录，不更改系统安装或默认应用。
- [ ] 执行 `deps/kicad/bin/kicad-cli.exe version`，记录实际路径/版本；确认Python pcbnew、标准symbols/footprints可加载。若压缩包目录不同则统一到该路径。
- [ ] 官方模块图建立坐标表；验证两排18孔的信号/电源映射，USB外形和接收器插拔净空。

### Task 2: 电路、模型和原理图

**Files:** hardware/carrier/（project、symbols、footprints、BOM、pinout）；tools/hardware/（生成/检查脚本）；tests/test_carrier_design.py。

**Interfaces:** hardware/carrier/design.json 为BOM/连接规范：components 按ref索引，含symbol/footprint/value/pins；pins 为引脚号→网络；placement 给PCB的X/Y/rotation。模块符号和封装本地库，所有低压扩展口有显式针序。生成器导出 carrier.kicad_sch、carrier.net 和bom.csv。

- [ ] 先验证关键连接：模块坐标映射、四路分压及RC无直通5V、按键和PWM芯片地址不同、FFB EN默认关断、全部连接器不含电机电源。

```python
self.assertEqual(model['components']['U1']['pins']['12'], 'ADC_THROTTLE')
self.assertEqual(model['components']['U1']['pins']['13'], 'ADC_BRAKE')
self.assertNotIn('MOTOR_VBUS', set(model['nets']))
```

- [ ] 对扩展器核对官方数据手册、复位/输出级/去耦/上拉和引脚封装；选能采购的具体型号，不用猜测库引脚。
- [ ] 生成真实可编辑KiCad原理图，再运行 `kicad-cli sch erc --exit-code-violations -o hardware/carrier/reports/erc.rpt hardware/carrier/carrier.kicad_sch`，逐项修复电气错误；所有未连接引脚有明确理由。
- [ ] 导出PDF/SVG和KiCad网表，核对模型与导出网表；记录原理图及电路审查。

### Task 3: PCB 布局布线

**Files:** hardware/carrier/carrier.kicad_pcb、板级规则/输出；tools/hardware/build_pcb.py。

- [ ] 先测试自定义模块脚位坐标、四个孔均在板内、端子与模块不重叠、USB和接收器方向有净空。

```python
self.assertAlmostEqual(module_right_x-module_left_x, 15.24)
self.assertEqual(len(module_pads), 18)
```

- [ ] 放置模拟端子和滤波，滤波电容靠近对应ADC；GPIO/PWM和SPI区与模拟回路分区，接收器不被连接器遮挡。
- [ ] 双层布线、地平面、明确5V/3V3与低压丝印、控制引脚默认下拉；最小线宽/间距、孔铜和电源宽度写入项目规则。
- [ ] 如用Freerouting，保留DSN/SES输入和版本，导回KiCad铺铜再检查，不把自动布线成功当作电气验证。
- [ ] 执行 `kicad-cli pcb drc --exit-code-violations --schematic-parity -o hardware/carrier/reports/drc.rpt hardware/carrier/carrier.kicad_pcb`，清除未连线及确定违规，导出板图与3D预览检查。

### Task 4: 交付与交接

**Files:** hardware/carrier/fabrication/、hardware/carrier/README.md、docs/reports/19-expandable-carrier-pcb.md、HANDOFF.md。

- [ ] 原理图/PCB复核通过后导出Gerber和钻孔，校验层数、外形、钻孔和网表一致性；为文件生成SHA256清单。
- [ ] 独立审查：ADC调理/供电、I²C/复位、FFB EN/接口边界、封装孔位、装配方向和3.3V/5V丝印；修复确定问题后重跑相应检查。
- [ ] 更新接线表、BOM、装配顺序、首次上电和验收步骤、固件适配清单；引用实际ERC/DRC证据。明确直驱尚未选型、本次无电机驱动子板且未投板/上电测试。
- [ ] 保留既有0.5.0源码/产物；本地功能分支保存工程，不推送或制造下单。
