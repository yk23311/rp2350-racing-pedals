# 15：GitHub公开仓库上传与交接

日期：2026-10-31（Asia/Shanghai）。用户要求将本项目推送GitHub，并明确选择“新建公开仓库，基于rp2350的赛车模拟器油门”。

## 已执行步骤

1. 检查Git状态、历史与远程：现有main分支含原生XInput/Host桥接历史，尚无远程；保留既有历史及所有项目改动。
2. 确认GitHub账号`yk23311`可访问，创建公开仓库[rp2350-racing-pedals](https://github.com/yk23311/rp2350-racing-pedals)，配置origin。
3. 重新运行发布前回归：43项CTest、61项Python全部通过，见[日志](logs/github-prepush-tests.txt)。
4. 检查待提交文件及既有历史，没有发现常见GitHub令牌/私钥/AWS访问密钥格式；无大于5MiB的候选文件。该检查不等于全面安全审计。
5. 使用现有`.gitignore`排除`.venv`、工具链deps、build、dist和缓存。提交源码、文档、测试、步骤日志与4张GUI演示截图。
6. 更新README的GitHub首次安装/预览步骤与相对图片链接，说明二进制需本地构建。
7. 提交`9b81c3f69f125388617c5f90b01dc41628afc9e7`并执行`git push -u origin main`成功。GitHub API已确认仓库PUBLIC、默认分支main，远端SHA与本地一致。

## 交接结果

- 仓库：https://github.com/yk23311/rp2350-racing-pedals
- 分支：main，已跟踪origin/main；本报告作为后续文档提交一并同步。
- 未创建Release、未上传本地dist二进制、未部署网站或烧录板卡。
- 固件仍为0.4.0-control-center，PC验证通过，实机/FH6验收未完成；本次Git上传不改变这些状态。
- 本地构建时manifest记录的旧HEAD/dirty是当时真实状态，不能把后续Git提交误写成构建时已经提交。

后续修改可正常提交后`git push`；新电脑先克隆并按照README创建`.venv`、安装固定依赖，构建固件前获取项目固定版本工具链。完整实现与待验收事项见[控制中心报告](14-control-center.md)与[HANDOFF](../../HANDOFF.md)。
