# 16：v0.4.0 Release上传、验证与交接

日期：2026-10-31（Asia/Shanghai）。用户明确要求“上传releases”。

## 发布结果

公开预发布版：[v0.4.0 驾驶控制中心与原生XInput桥接](https://github.com/yk23311/rp2350-racing-pedals/releases/tag/v0.4.0)。已确认`draft=false`、`prerelease=true`，不是未发布草稿。

Tag固定源码提交：`340b33fdbb05dfc4626fdb0c1546fec8d0864cfb`。后续本报告的文档提交不会移动Tag或改变已发布产物。

## 步骤报告

1. 检查仓库已有Release为空、工作区干净，远端main与本地源码提交一致。
2. 从已提交版本重新构建普通/诊断固件，manifest确认源码HEAD匹配、`source_dirty=false`，链接结束点均小于0x101FE000。
3. 发布前重新回归：43项CTest、61项Python通过。使用Release附件中的test-results-v0.4.0.txt保留该轮日志。
4. 校验bin/elf/map/uf2清单，并用同一打包函数验证UF2与对应bin逐字节一致；Git archive从固定提交生成完整源码包，含Qt GUI但不含本地环境/工具链。
5. 上传7个附件到草稿，检查附件名/大小与目标提交。
6. 从GitHub重新下载全部附件；SHA256SUMS本身与本地逐字节相等，其余6个文件与本地字节及校验值全部相符。
7. 公开发布为预发布版，并通过GitHub CLI读取发布状态和URL确认。

## 附件

| 文件 | 用途 |
|---|---|
| pedals-bridge-v0.4.0.uf2 | 普通日用固件 |
| pedals-bridge-debug-v0.4.0.uf2 | 专用诊断固件 |
| rp2350-racing-pedals-v0.4.0-source.zip | 完整源码，含Qt GUI、文档、测试、截图；需要Python与固定依赖，不是独立exe |
| quickstart-v0.4.0.md | 下载选择、烧录、GUI安装与配置迁移说明 |
| build-manifests-v0.4.0.json | 干净源码提交、两版本构建清单/哈希及配置边界 |
| test-results-v0.4.0.txt | 本轮43项C、61项Python测试日志 |
| SHA256SUMS.txt | 其余6个附件的SHA256 |

## 交接与边界

日常选择普通UF2，GUI从源码包安装并双击启动脚本。没有执行烧录或硬件/FH6验收，发布说明与manifest均明确保留未实机验证状态，因此使用预发布标记，没有宣称稳定硬件版本。

先备份校准；新固件可读PDL1，SAVE后写PDL2，旧固件不识别新记录。完整使用说明见[控制中心指南](../control-center.md)，实现与待验收见[阶段14](14-control-center.md)。

本地附件在`dist/releases/v0.4.0`，下载核验副本在`dist/release-verify/v0.4.0`，均被Git忽略；它们已通过Release分发，不添加到Git源码历史。
