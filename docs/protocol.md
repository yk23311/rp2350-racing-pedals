# CDC协议 v1

115200波特率为主机串口设置，USB CDC本身不以UART波特率传输。主机应置DTR。ASCII逐行、LF结束，可接受CRLF；命令最多127字符，不带终止符。每次只发送一条命令并等待完整响应。

| 命令 | 响应/行为 |
|---|---|
| `PING <32位小写十六进制token>` | `OK {"sync":"<token>"}`，建立会话，排除上次连接的残留响应 |
| `GET` | `OK {...}` JSON状态，含protocol/mode/armed/calibration_axis/raw/filtered/output/axes |
| `SET axis on off gamma window` | 校验通过原子更新RAM，清滤波、输出中立，需松开重新使能 |
| `CAL axis BEGIN` | 全松开位置开始专用校准，期间所有输出中立 |
| `CAL axis END` | 踩到底并保持时结束；小于128 counts拒绝，保留原配置，会话可重试或CANCEL |
| `CAL axis CANCEL` | 取消当前对应轴的校准，不更改旧参数 |
| `MODE JOYSTICK` / `MODE KEYBOARD` | 固定枚举不变，切换逻辑；先中立、回零后重新输出 |
| `SAVE` | 仅采样有效、已使能、无校准且双轴中立时尝试持久化；USB中立未完成也会拒绝 |
| `DEFAULTS` | 仅RAM恢复默认未校准配置；校准中拒绝；需SAVE才影响重启 |

成功无数据返回 `OK\n`。错误返回 `ERR COMMAND`、`ERR STATE_OR_VALUE` 或 `ERR TOO_LONG_OR_BINARY` 等。收到错误不能假设发生了参数修改或保存。超长/二进制输入整行丢弃直到LF，下一行正常恢复。

axis：0油门/1刹车；0≤off<on≤5000（万分比），gamma100–400（1.00–4.00），window1–8。端点只经校准产生，防止上位机任意填值导致未验证输出。导出JSON用于审阅和备份，本版不提供端点JSON导入。

正常模式冻结校准；端点大小决定方向。keyboard发W/S，并直接使用行程迟滞状态，避免幂曲线量化改变触发阈值。模式不会写Flash，重启总是JOYSTICK。

板端记录40字节：`PDL1` magic，16位version=1、16位length=40、32位sequence，两个12字节轴配置，末尾32位CRC。全部字段小端；每轴 released/pressed/on/off/gamma 各16位、window与calibrated各8位。CRC为IEEE CRC32，覆盖前36字节。双槽序号比较支持32位回绕；同序号优先槽0。
