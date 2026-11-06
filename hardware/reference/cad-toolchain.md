# 本地 CAD 工具链

核对日期：2026-11-06。本项目使用从官方 Windows 发布包提取的 KiCad 10.0.8。工具、用户配置及验证样件均在忽略的 `deps/` 中。没有运行 NSIS 安装器，没有进行系统安装或修改文件关联。

## 来源与安装包验证

- [官方 Windows 下载页](https://www.kicad.org/download/windows/)：本次读取的稳定版为 10.0.8。
- [官方页面指向的 Alibaba 镜像安装包](https://mirrors.aliyun.com/kicad/windows/stable/kicad-10.0.8-x86_64.exe)。下载使用 `curl.exe -L --fail --retry 2`，写入 `deps/kicad-10.0.8-x86_64.exe`。
- [官方签名验证说明](https://www.kicad.org/help/windows-download-verification/)。提取前使用 `Get-AuthenticodeSignature` 检查状态、签名者、颁发者和序列号，全部通过后才调用 7-Zip。

| 项目 | 实际结果 |
| --- | --- |
| 安装包大小 | 969,079,176 bytes |
| SHA256 | `5652b9ed52fca4aa63ec2ec61c8bfd4fab4f6a2fbfdb441def2972b0e9b2dfc7` |
| Authenticode | `Valid` / `Signature verified.` |
| 签名者 | `KICAD SERVICES CORPORATION` |
| 颁发者 | `GlobalSign GCC R45 EV CodeSigning CA 2020` |
| 官方证书序列号 | `39DF6B588D969CA15D8D2756` |
| 证书指纹 | `4FF2AE9EC27A37207CBEB533EFCEE1F689C9AAAC` |
| 验证时间 | `2026-11-06T13:03:26+08:00` |

归档已设为只读。详细证书记录与摘要保留于 `deps/kicad/verification/installer-verification.json` 和 `installer.sha256`；可执行 `verification/verify-installer.ps1` 重新检查。证书有效期按本机东八区显示，UTC 日期与官网日期一致。

## 提取与目录

使用本机 `C:/Program Files/7-Zip/7z.exe` 26.03，只解包，没有执行安装器。第一轮提取排除了全部 `3dmodels`、`doc` 和安装插件目录，保留二进制、运行库、Python、符号、封装和配置模板：

```powershell
& 'C:\Program Files\7-Zip\7z.exe' x 'deps\kicad-10.0.8-x86_64.exe' '-odeps\kicad' '-y' '-xr!3dmodels' '-xr!doc' '-xr!$PLUGINSDIR'
```

实际根目录无需重排：

| 用途 | 项目内路径 |
| --- | --- |
| CLI | `deps/kicad/bin/kicad-cli.exe` |
| Python | `deps/kicad/bin/python.exe`，版本 3.11.5 |
| pcbnew | `deps/kicad/bin/Lib/site-packages/pcbnew.py` |
| 官方符号 | `deps/kicad/share/kicad/symbols/`，223 个 `.kicad_sym` |
| 官方封装 | `deps/kicad/share/kicad/footprints/`，155 个 `.pretty` 库 |
| 用户配置 | `deps/kicad/user-config/10.0/` |
| 用户文档 | `deps/kicad/user-documents/` |
| 选用的 3D 模型 | `deps/kicad/share/kicad/3dmodels/` |

官方 `template/sym-lib-table` 和 `template/fp-lib-table` 已复制到上述项目内用户配置。第一轮提取 23,521 个文件，合计 1,416,029,876 bytes；归档清单和提取日志位于 `deps/kicad/verification/archive-contents.txt`、`extraction.log`。

## 运行方法

在项目根目录打开 PowerShell：

```powershell
. '.\deps\kicad\env.ps1'
& '.\deps\kicad\bin\kicad-cli.exe' version
& '.\deps\kicad\bin\python.exe' -I '.\deps\kicad\verification\smoke.py'
```

`env.ps1` 仅为当前 PowerShell 进程设置 `KICAD_CONFIG_HOME`、`KICAD_DOCUMENTS_HOME`、`KICAD_STOCK_DATA_HOME`、`KICAD10_SYMBOL_DIR`、`KICAD10_FOOTPRINT_DIR` 和 `KICAD10_3DMODEL_DIR`，全部指向本项目。Python 使用 `-I` 隔离模式即可直接导入随包 `pcbnew`，无需安装 Python 包或设置 `PYTHONPATH`。中文项目路径已实际读写成功。

受限环境下 `kicad-cli` 会打印无法创建/打开 `HKCU\Software\kicad-cli` 的 wxWidgets 注册表诊断，随后正常执行；本次版本、符号导出、SVG、3D 和 DRC 命令退出码均为 0。没有为消除诊断而提升权限或写入注册表。最初未设置用户文档路径的探测也被沙箱拒绝；正式调用先加载 `env.ps1`，将用户文档定位到项目内。

## 引擎验证

实际执行结果保留于 `deps/kicad/verification/`，这些是工具自检样件，不代表底板工程的 ERC/DRC 结论。

| 检查 | 实际结果 / 记录 |
| --- | --- |
| `kicad-cli version` | 10.0.8；`version.log` |
| `pcbnew` 导入 | 10.0.8；`pcbnew-smoke.log` |
| 标准封装加载、建板、保存、读回 | R_0805_2012Metric；读回 1 个封装、4 条 Edge.Cuts；`smoke.py`、`smoke.kicad_pcb` |
| 标准符号加载 | Device:R 成功导出 `symbols/R_unit1.svg`；`symbol-load.log` |
| PCB SVG 导出 | 成功生成 `smoke.svg`；`svg-export.log` |
| PCB 3D 光线追踪 | 成功生成并查看 `smoke.png`，640×400，包含实际 R0805 STEP 模型；`render.log` |
| PCB DRC 引擎 | 样件 0 违规、0 未连接；`smoke-drc.rpt`、`drc-smoke.log` |
| 所需 CLI 命令 | `sch erc`、`pcb drc --schematic-parity --exit-code-violations`、`pcb export svg`、`pcb render` 的帮助均已实际调用，保留 `help-*.txt` |

SVG 单文件导出使用 `--mode-single -o 路径/文件.svg`；此模式的 `-o` 实际要求文件名。

[KiCad 10 CLI 文档](https://docs.kicad.org/10.0/en/cli/cli.html)列出本项目使用的命令。[官方 pcbnew 接口说明](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html)明确 SWIG 已弃用、计划 KiCad 11 移除；本项目固定 10.0.8，未声称兼容 11。

## 最小 3D 模型集合

从实际 `hardware/carrier/design.json` 的唯一封装出发，读取随包 `.kicad_mod` 中的模型引用，再从同一个已验证安装包精确提取 12 个官方 STEP 文件，合计 1,927,282 bytes。目录保留官方层级，由 `KICAD10_3DMODEL_DIR` 解析：

- `Capacitor_SMD.3dshapes/C_0805_2012Metric.step`
- `Resistor_SMD.3dshapes/R_0805_2012Metric.step`
- `Fuse.3dshapes/Fuse_1206_3216Metric.step`
- `Diode_SMD.3dshapes/D_SOD-323.step`
- `Package_SO.3dshapes/SOIC-24W_7.5x15.4mm_P1.27mm.step`
- `Package_SO.3dshapes/TSSOP-28_4.4x9.7mm_P0.65mm.step`
- `TerminalBlock_Phoenix.3dshapes/TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal.step`
- `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x02_P2.54mm_Vertical.step`
- `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x03_P2.54mm_Vertical.step`
- `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x04_P2.54mm_Vertical.step`
- `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x09_P2.54mm_Vertical.step`
- `Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x05_P2.54mm_Vertical.step`

精确清单与日志：`deps/kicad/verification/model-files.txt`、`model-extraction.log`。可重复提取：

```powershell
& 'C:\Program Files\7-Zip\7z.exe' x 'deps\kicad-10.0.8-x86_64.exe' '-odeps\kicad' '-y' '-i@deps\kicad\verification\model-files.txt'
```

自定义 RP2350 模块模型不属于官方模型集合；若工程以代理几何显示模块，不把代理高度、USB 外壳及插拔空间当作实测机械结论。

## 布线工具

最终布线使用 [Freerouting官方v2.1.0](https://github.com/freerouting/freerouting/releases/tag/v2.1.0) Java JAR，SHA256：`2c07d58f75dac03782664081e7a58b41c25400d871a9fcf166a2ea6fe60d5def`；官方旧版本发布未提供摘要，该值为本次下载后本地记录，不能冒充官方签名。Java21兼容性根据该版本官方build.gradle确认。使用系统已有Microsoft JDK21，无新增全局Java安装。

原始KiCad DSN完整保留铜箔、螺钉禁布区、焊盘和网络；未通过删除实际约束来完成布线。关闭云端API、GUI和匿名统计，本地生成SES后导回KiCad，并以KiCad最终DRC/原理图一致性复核为准。完整命令见 `tools/hardware/export_carrier.ps1` 与 `hardware/carrier/reports/autoroute.log`。

工具选择说明：v2.5.0 Windows原生CLI存在GraalVM类型序列化错误；本次改用Java稳定版。该工具失败不表示电路缺陷，也不作为任何电气检查通过依据。离线环境中的版本检查HttpClient可能产生非致命日志，实际布线作业与KiCad检查有独立完成记录。
