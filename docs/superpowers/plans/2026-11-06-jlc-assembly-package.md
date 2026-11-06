# 嘉立创 PCB 与贴片装配资料实施计划

> For agentic workers: execute this dependent export task in the current approved carrier checkout; verify each checkpoint before delivery.

**Goal:** 为用户已选择的嘉立创 PCB＋贴片装配提供可上传资料与明确的插件报价说明。

**Architecture:** 不修改 V0.1 电路、布线和固件。KiCad CLI 从同一原板重新导出 RS-274-X 和原生 SMT 坐标；Python 整理 CSV、比对原始图形流、核对物料/位号、打包并保存证据。

**Tech Stack:** KiCad 10.0.8 CLI、PowerShell、Python 标准库 unittest/csv/hashlib/zipfile。

## Global constraints

- 继续使用 `codex/expandable-carrier`，不创建新工作树，不提交或付款任何制造订单。
- 原板100×80mm、2层、1.6mm、1oz；现有 CAD、制造包及其摘要保持不变。
- 仅生成单面53个SMT器件的自动上传 BOM/CPL；U1模块、14个插件位和两条排母另外说明，安装孔不作为采购器件。
- JP1针座可装，短路帽不装；用户已有RP2350模块由用户最终插入，不把模块误当一个待SMT器件。
- 嘉立创元件编号不得猜测；不宣称已取得库存、报价、DFM审核或下单结果。
- 所有坐标以原生KiCad毫米坐标导出，保留Y轴符号；只归一化角度，不猜测工厂封装旋转修正。
- 不自动承诺插件代焊，给出单独清单和排母位置图，需由工厂确认可装配与报价。

## Task 1：验证并导出下单资料

Files: `tools/hardware/package_jlc.py`, `tools/hardware/export_jlc.ps1`,
`tests/test_jlc_package.py`, `hardware/jlc-v0.1/*`, `docs/reports/20-jlc-assembly-package.md`。

- [x] 先写失败测试：BOM/CPL位号一一对应；重复或缺失坐标拒绝；不包含模块/通孔/孔位；电容电阻规格和IC封装保留；非法数值/底层拒绝；X2与RS-274-X几何等价而真实走线变化拒绝。
- [x] 执行 `.venv/Scripts/python.exe -m unittest discover -s tests -p test_jlc_package.py -v`，确认缺少实现导致失败。
- [x] 实现分组BOM、坐标、插件说明及兼容导出：CLI `pcb export gerbers --no-x2 --no-netlist`；`pcb export pos --side front --format csv --units mm --smd-only --exclude-fp-th --exclude-dnp`。
- [x] 原生ERC/DRC+parity写入独立build目录，必须退出0；与原制造包逐层比较忽略注释/属性的绘图流；原钻孔字节不变。
- [x] 输出 `dist/carrier-jlc-v0.1/01-PCB-Gerber-RS274X.zip`、独立BOM/CPL、插件清单及完整资料ZIP；保留精确来源摘要、图形摘要和未完成工厂审核状态。
- [x] 执行新增测试和完整Python回归；核对CSV/ZIP与原板坐标、芯片1脚和文件摘要；记录实际命令/结果。
- [x] 完成中文下单步骤、报价话术、阶段20交接，独立复核；随本阶段本地提交保存，不推送。

## 官方资料（2026-11-06核对）

- 文件要求：https://www.jlc.com/portal/2/serviceGuide
- 下单流程：https://docs.lceda.cn/cn/PCB/Order-PCB/index.html
- 坐标规范：https://www.jlc.com/portal/q7i53182.html
- SMT/插件能力：https://www.jlc-smt.com/vtechnology
- KiCad坐标说明：https://jlcpcb.com/help/article/how-to-generate-the-bom-and-centroid-file-from-kicad

本次只是将已批准的工程样板适配所选厂商，不涉及新的电路方案或扩展功能批准。
