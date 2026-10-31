# 双踏板实施计划

> 执行方式：本会话按 executing-plans 顺序实施；各任务先写失败测试，再实现并更新报告。用户已授权审核后开工。

**Goal:** 交付可验证的双踏板软件首版和硬件接入交接材料。

**Architecture:** 纯 C 核心独立于 Pico HAL 和 TinyUSB。电脑 CLI 与 CDC 协议配合，Flash 显式双槽保存。

**Tech Stack:** C11、CMake、Pico SDK 2.2.0、配套 TinyUSB、Python 3.11 标准库（串口连接用 pyserial）。

## 全局约束

- 默认未校准中立；未经电压核实不接入传感器。
- 两个轴、1 ms 目标周期、窗口 1–8、迟滞 3%/1%、16-bit HID 格式。
- 不自动烧录、不改系统驱动；不把软件测试标为硬件通过。
- 当前目录无 Git 仓库，保留本地文件和验证记录，不虚构提交。

## 阶段和完成条件

- [x] 01 审核：核查 SDK/官方资料，记录方案纠正、型号信息与未决电气条件。
- [x] 02 核心：`include/pedal.h`、`src/core/pedal.c`、`tests/test_core.c`。实现配置验证、滤波、双向映射、迟滞、曲线、校准、模式、按键状态。PC CTest 通过。
- [x] 03 配置与协议：`include/config_record.h`、`src/core/config_record.c`、`include/console.h`、`src/core/console.c`。固定格式序列化、CRC、双槽选择、严格命令校验；损坏/截断/非法参数测试通过。
- [x] 04 硬件适配：`firmware/` 内 ADC、GPIO、Flash、USB 描述符与主循环；指定板型构建成功。原生 USB 枚举与实际电路留待上板执行。
- [x] 05 上位机和交接：`tools/pedalctl.py` 支持参数查询、配置、校准、保存、JSON 导出及采样记录；另有Tkinter滑条GUI。`docs/reports/` 每阶段步骤和交接均已完成，硬件和验收文档齐备。

## 执行顺序与测试契约

1. 建立 CMake host 模式和 `tests/test_core.c`，先验证目标映射/迟滞断言能失败；添加纯 C 实现使其通过。
2. 配置编码测试检查 byte-exact roundtrip、CRC翻转、截断、非法字段、序号回绕；控制台测试检查非法数字、超长行、原子更新及 SAVE 受限。先失败后实现。
3. 从本地 SDK 官方板型定义构建；USB descriptor 测试核对接口数、总长度、endpoint 唯一性、16-bit unsigned axis logical maximum。检查 Flash 最后 8 KiB 不进入程序链接区域。
4. Python 工具先用模拟串口契约测试 GET/ERR/timeout/导出路径，再实现串口适配。验证 CLI help 和无硬件单元测试。
5. 实际使用 `tools/build_host.ps1` 运行Clang/LLD Release构建、CTest和Python测试；原MSVC Debug环境因MSPDB140.DLL异常未采用。日志归档；C13项和Python14项通过。固件成功构建仅报告编译状态，不替代上板验收。

## 硬件阶段（有前置条件的后续工作）

用户确认传感器信号和接线 → 电压台架验收 → UF2 烧录 → CDC 原始值 → 两轴校准 → joy.cpl → 键盘模式及释放 → SAVE/重启/掉电恢复 → 1小时漂移 → 目标游戏。每项填写实际数据和日期，未执行保持未验收。
