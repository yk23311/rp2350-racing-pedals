# 原生Xbox扳机固件使用说明

当前版本：0.2.0-xinput。油门GP26→右扳机RT，刹车GP27→左扳机LT，均为0–255模拟量，可以同时输入。设备直接提供USB XInput协议，由Windows内置xusb22驱动读取，不使用Steam Input、虚拟手柄软件或电脑映射器。

## 使用步骤

1. 原固件中未保存的参数先回零并保存到Flash；已保存校准记录与新固件共用。
2. 按住BOOT连接Type-C，将 `dist/xinput/pedals-xinput.uf2` 复制至BOOTSEL磁盘，等待自动重启。不要复制旧的 `dist/pedals.uf2`，那是旧HID版本。
3. Windows设备管理器应出现“支持 Windows 的 XBOX 360 手柄”，服务为xusb22。新开发VID/PID为CAFE:4012，CDC串口号可能变化。本次实机为COM8。
4. 如需调参，重开GUI、填写新串口号。正常手柄模式仍用兼容命令 `MODE JOYSTICK`，在新固件中表示原生RT/LT；`GET`的`usb_transport`应为`XINPUT`。玩游戏不必运行调参工具。
5. 退出游戏，在Steam游戏属性→控制器中禁用Steam Input，然后重启游戏，使用Xbox手柄默认RT加速/LT刹车。此前排查误启用了此游戏的Steam Input，后续由用户关闭；不再自动操作Steam界面。

## 验证独立扳机

```powershell
Set-Location -LiteralPath 'D:\练习项目\RP2350a'
.\.venv\Scripts\python.exe tools/check_xinput.py --seconds 30
```

这个工具只调用系统`XInputGetState`读取数值，不产生虚拟设备、不做映射，也不发送按键。系统正常终端可直接使用；受限沙箱可能禁止读取控制器。

期望值：全松开LT=RT=0；仅油门到底RT=255/LT=0；仅刹车到底LT=255/RT=0；同时到底LT=RT=255。joy.cpl的旧DirectInput视图可能合并两扳机，验收以XInput读取的独立值为准。有其他手柄时，槽位0–3中需通过实际踩踏确定本设备；脚本不假定所有Xbox控制器都是本设备。

本设备是一只独立XInput控制器，并非把输入合并到另一只实体手柄。后续若需要实体手柄负责转向并与踏板合用，还需单独验证游戏的多控制器行为。

## 构建与回退

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode xinput
powershell -ExecutionPolicy Bypass -File tools/build_firmware.ps1 -UsbMode hid
```

分别输出 `dist/xinput/pedals-xinput.uf2` 和 `dist/hid/pedals-hid.uf2`。旧版交付产物也保留在dist根目录。新固件仍只使用物理2MiB Flash中配置区之前的程序区域，末尾8KiB配置格式未更改。

## 实现依据

- [Microsoft MS-XUSBI OS descriptor](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-xusbi/601a3107-6583-4e80-867e-118829cb573e)：接口0通过XUSB10匹配内置有线Xbox驱动。没有复制微软VID或厂商名称。
- [Microsoft XUSB默认输入报告](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-xusbi/e79d4543-9614-4db7-9321-f018575e30e3)：20字节，LT在offset4、RT在offset5。
- [SDL作者实现](https://raw.githubusercontent.com/libsdl-org/SDL/main/src/joystick/hidapi/SDL_hidapi_xbox360.c)：交叉核对PC的能力查询；未把该源码当作微软完整协议定义。

此实现目标是Windows PC，不承诺Xbox主机认证、振动马达或完整实体手柄的按钮功能。
