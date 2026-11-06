# 20：嘉立创 PCB＋贴片装配资料：步骤与交接报告

2026-11-06。用户选择嘉立创，并确认“PCB＋贴片装配”。沿用阶段19已批准的V0.1电路/PCB，未修改固件、CAD或原制造包。**本次完成可上传PCB/SMT资料与插件询价说明，尚未取得订单库存、工厂DFM、插件装配报价或实物验收。**

## 步骤报告

1. 核对嘉立创官方文件要求、PCB/SMT流程、坐标格式与插件工艺能力。官方文件要求说明使用RS-274-X，因此从同一KiCad板另导出 `--no-x2 --no-netlist`，没有手工修改走线或删减孔位。
2. 先写6项制造交付合同测试：53位号覆盖、缺失/重复拒绝、模块/插件排除、准确器件参数、坐标合法性、图形属性等价与真实图形变化区分。执行得到6项失败，原因是导出实现不存在；实现后6项通过。
3. 新增 `tools/hardware/export_jlc.ps1` 与 `package_jlc.py`。原生ERC/DRC+原理图一致性写入独立build目录并作为导出门禁。重新执行结果0违规、0未连接、0一致性问题，CLI全部退出0。沙箱下KiCad的用户注册表读取/创建告警不影响这些原生检查退出结果。
4. 九层新RS-274-X与原X2逐层比较：忽略注释和X2属性后的全部绘图指令/宏内容完全相同；两个原始PTH/NPTH钻孔直接复制，字节未变。01 PCB包只有九层Gerber及两个钻孔，共11个制造文件。
5. 原生CLI以mm输出顶面SMD坐标，排除带通孔/不装配器件。包内02 BOM为9组53个器件，03为53条一位号一行坐标。核对位号、值、封装、数值与原审查placement；保留KiCad的负Y，不猜工厂旋转补偿。
6. 插件单列：J1-J13/JP1共14个物理插件，另U1两条1×9排母，合计16个。04为询价/后焊清单，明确不能与03直接当一套自动SMT上传。U1模块用户自有、最终插接；JP1不装短路帽。给出两排母图，PCB坐标中心分别(15.04,11.13)/(15.04,26.37)，未确认排母高度，不把示意3D高度当采购尺寸。
7. 原生pcbnew额外查看U2/U3的1脚，均在顶视图左上：U2板坐标(43.35,37.015)，U3(80.1375,36.775)mm。装配文档说明准确宽体SOIC-24与TSSOP-28封装；厂家物料库零度需在实际匹配后的预览/DFM核对。
8. 完整Python回归124项通过（原118＋新增6）。排母SVG使用本机Arial显式加载后栅格化并目视检查，字号/方向/孔数/注释可读。预览PNG仅存在build作检查，不冒充精确机械图。
9. 独立只读复核确认原manifest、两份ZIP内容/CRC/摘要、九层图形、钻孔、BOM/CPL与U1孔位一致，未发现阻碍询价/上传的制造缺陷。发现一项测试修改了U2却检查原样C1，已改为明确选C1并输入不同坐标；内存故障注入取消角度归一化后，修正测试如预期失败，真实实现重新运行124项通过（5.331s）。制造资料未因该测试修正改变。

实际验证命令：`tools/hardware/export_jlc.ps1`退出0；`.venv/Scripts/python.exe -m unittest discover -s tests -q`为124项通过；故障注入只在临时Python模块内执行，没有修改生产源码或CAD。

## 文件入口

- [一步步嘉立创下单说明](../../hardware/jlc-v0.1/README.md)
- [装配工程说明](../../hardware/jlc-v0.1/05-assembly-notes.md)
- [两条模块排母位置图](../../hardware/jlc-v0.1/06-module-sockets.svg)
- `hardware/jlc-v0.1/02-BOM-SMT.csv`：9组/53个顶面SMT。
- `hardware/jlc-v0.1/03-CPL-SMT.csv`：53条原生坐标，全部Top，mm。
- `hardware/jlc-v0.1/04-DIP-quote-only.csv`：16个插件询价，非自动SMT上传BOM。
- `hardware/jlc-v0.1/verification.json`：原板/原审查摘要、九层绘图流SHA256、实际验证与未完成工厂环节。
- `hardware/jlc-v0.1/checks/`：本次原生ERC/DRC JSON。
- `dist/carrier-jlc-v0.1/01-PCB-Gerber-RS274X.zip`：PCB页面只上传此文件。
- `dist/carrier-jlc-v0.1/carrier-jlc-v0.1-order-files.zip`：完整下载资料包，解压后分步骤上传。
- `dist/carrier-jlc-v0.1/SHA256SUMS.txt`：两份ZIP摘要。

## 交接报告

1. 用户登录嘉立创，下载完整资料包解压；PCB识别框只上传01，不上传整个资料包或旧X2通用包。按README填写2层、100×80mm、1.6mm、1oz等参数，选择需要SMT。
2. SMT对应上传02/03，逐组核对元件型号和封装。LCSC编号故意留空：未在用户账号里匹配库存，不能宣称已完成配料。原厂型号带逗号已CSV转义。
3. 用户如果不想自己焊接，必须把04/05/06交给嘉立创工程确认插件代焊、排母高度匹配和备料；只下53件SMT不会得到完整接线端子。插件库存、工艺边/Mark和装配服务以本单工程确认结果为准。
4. 确认报价、工厂修正后的元件方向和生产稿/DFM，再按平台流程授权生产。没有代用户提交订单、付款、邮寄器件或发送消息。
5. 收货依阶段19验板、先查短路和电源后插模块，逐路恢复原有双踏板和手柄桥接。底板未上电验证；不直接连接MiGE电机，新扩展仍需软件适配。

源码在现有 `codex/expandable-carrier`，没有新工作树或远程发布。旧 `dist/carrier-v0.1/` 仍为阶段19通用工程快照，本次嘉立创资料入口是独立的 `dist/carrier-jlc-v0.1/`。

## 官方资料

- [客户下单文件类型](https://www.jlc.com/portal/2/serviceGuide)
- [嘉立创EDA PCB/SMT下单流程](https://docs.lceda.cn/cn/PCB/Order-PCB/index.html)
- [坐标文件格式规范解读](https://www.jlc.com/portal/q7i53182.html)
- [嘉立创SMT工艺能力](https://www.jlc-smt.com/vtechnology)
