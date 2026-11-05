"""Focused device test and firmware update widgets; no serial ownership."""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)
try:
    from .control_widgets import BUTTONS, BITS, StickView
except ImportError:
    from control_widgets import BUTTONS, BITS, StickView


def text_label(text, name="muted"):
    label = QLabel(text); label.setObjectName(name); label.setWordWrap(True)
    return label


def panel(title, subtitle):
    frame = QFrame(); frame.setObjectName("card")
    layout = QVBoxLayout(frame); layout.setContentsMargins(20,17,20,17); layout.setSpacing(10)
    layout.addWidget(text_label(title,"sectionTitle")); layout.addWidget(text_label(subtitle))
    return frame, layout


class DeviceTestPage(QWidget):
    command_requested = Signal(str)

    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.completed_mask = self._held_mask = 0
        self._can_start = self._can_stop = False
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,10)
        row = QHBoxLayout(); row.setSpacing(16); layout.addLayout(row)
        buttons, box = panel("实体按键检查", "读取接收器原始输入 · 每个按钮按下再松开一次")
        header = QHBoxLayout(); self.checklist_summary = text_label("0 / 14 已完成","sectionTitle")
        header.addWidget(self.checklist_summary); header.addStretch()
        self.clear_button=QPushButton("清空记录"); self.clear_button.clicked.connect(self.clear_history)
        header.addWidget(self.clear_button); box.addLayout(header)
        grid=QGridLayout(); grid.setSpacing(8); self.button_labels=[]
        for i,name in enumerate(BUTTONS):
            label=text_label(name+"  ·  待检查","bindingSource"); label.setMinimumWidth(110)
            grid.addWidget(label,i//2,i%2); self.button_labels.append(label)
        box.addLayout(grid)
        self.input_status=text_label("输入不可用 · 等待连接手柄"); box.addWidget(self.input_status)
        box.addStretch(); row.addWidget(buttons,1)
        right=QVBoxLayout(); row.addLayout(right,1)
        axes,axisbox=panel("摇杆与扳机", "真实手柄 Raw · 无需电脑端映射")
        axisbox.setSpacing(6)
        sticks=QHBoxLayout(); self.sticks=[]
        for title in ("左摇杆","右摇杆"):
            col=QVBoxLayout(); col.addWidget(text_label(title),0,Qt.AlignCenter)
            view=StickView(); view.setFixedSize(100,100); self.sticks.append(view)
            col.addWidget(view); sticks.addLayout(col)
        triggerbox=QVBoxLayout();triggerbox.setSpacing(6);sticks.addLayout(triggerbox,1)
        self.triggers=[]
        for title in ("LT","RT"):
            label=text_label(title+"  —"); bar=QProgressBar(); bar.setRange(0,255);bar.setTextVisible(False)
            triggerbox.addWidget(label);triggerbox.addWidget(bar);self.triggers.append((label,bar))
        triggerbox.addStretch();axisbox.addLayout(sticks)
        right.addWidget(axes)
        rumble,rumblebox=panel("限时震动测试", "板端计时自动停止 · 默认低强度、短时长")
        rumblebox.setSpacing(6)
        controls=QGridLayout();self.left_spin=self._spin(0,100,25," %")
        self.right_spin=self._spin(0,100,25," %"); self.duration_spin=self._spin(100,3000,500," ms")
        for i,(title,spin) in enumerate((("左马达",self.left_spin),("右马达",self.right_spin),("持续时间",self.duration_spin))):
            controls.addWidget(text_label(title),0,i);controls.addWidget(spin,1,i)
        rumblebox.addLayout(controls)
        actions=QHBoxLayout();self.start_button=QPushButton("开始震动测试");self.start_button.setObjectName("primary")
        self.stop_button=QPushButton("立即停止");actions.addWidget(self.start_button);actions.addWidget(self.stop_button)
        self.start_button.clicked.connect(self.start_rumble);self.stop_button.clicked.connect(self.stop_rumble)
        rumblebox.addLayout(actions)
        self.rumble_status=text_label("连接支持 RUMBLE TEST 的固件后可测试。");rumblebox.addWidget(self.rumble_status)
        self.rumble_detail=text_label("转发状态 —");rumblebox.addWidget(self.rumble_detail)
        right.addWidget(rumble);right.addStretch()
        layout.addWidget(text_label("USB OUT 传输成功仅表示接收器已接收 USB 数据，不是无线手柄马达确认。"))
        self.set_context(False,False,{},None)

    @staticmethod
    def _spin(lo,hi,value,suffix):
        spin=QSpinBox();spin.setRange(lo,hi);spin.setValue(value);spin.setSuffix(suffix);return spin

    def clear_history(self):
        self.completed_mask=self._held_mask=0
        self.update_buttons(0,False)

    def update_buttons(self, mask, fresh):
        physical=sum(1<<bit for bit in BITS)
        mask=(int(mask)&physical) if fresh else 0
        if fresh:
            self.completed_mask |= self._held_mask & ~mask
            self._held_mask=mask
        else:
            # Invalidate the entire unfinished gesture on any freshness gap.
            self._held_mask=0
        for name,bit,label in zip(BUTTONS,BITS,self.button_labels):
            pressed=bool(mask&(1<<bit));complete=bool(self.completed_mask&(1<<bit))
            label.setText(f"{name}  ·  "+("按下" if pressed else "✓ 已完成" if complete else "待检查"))
            label.setProperty("pressed",pressed)
            label.style().unpolish(label);label.style().polish(label)
        self.checklist_summary.setText(f"{self.completed_mask.bit_count()} / 14 已完成")
        self.input_status.setText("演示输入 · 仅本地预览" if self.demo else "原始输入有效 · 按下后松开以完成检查" if fresh else "输入不可用 / 已过期 · 未完成的按下已取消")

    def update_input(self,pad,fresh):
        valid=isinstance(pad,(list,tuple)) and len(pad)>=7
        if not valid:pad=[0]*7
        fresh=bool(fresh and valid)
        self.update_buttons(pad[0],fresh)
        for i,stick in enumerate(self.sticks):stick.set_value(pad[3+2*i],pad[4+2*i],fresh)
        for i,(label,bar) in enumerate(self.triggers):
            label.setText(f"{('LT','RT')[i]}  {pad[i+1]/255*100:.1f}%" if fresh else f"{('LT','RT')[i]}  —")
            bar.setValue(pad[i+1] if fresh else 0)

    def set_context(self,connected,fresh,capabilities,rumble,busy=False):
        status=rumble or {}
        supported=bool(capabilities.get("rumble_test"))
        self._can_stop=bool(connected and supported and not self.demo and not busy)
        self._can_start=bool(self._can_stop and fresh and status.get("available") and status.get("enabled") and not status.get("faulted"))
        self.start_button.setEnabled(self._can_start);self.stop_button.setEnabled(self._can_stop)
        for spin in (self.left_spin,self.right_spin,self.duration_spin):spin.setEnabled(not busy)
        self.rumble_status.setText("演示模式 · 不会向设备发送命令" if self.demo else "固件升级中 · 测试暂停" if busy else
            "当前固件不支持震动测试 · 请升级至桥接版 0.5.0" if not supported else
            "设备未连接 · 最近状态仅供参考" if not connected else
            "状态已过期 · 可立即停止，等待新数据后开始" if connected and not fresh else
            f"正在测试 · 剩余 {status.get('remaining_ms',0)} ms" if status.get("testing") else
            "故障已锁定 · 请检查接收器连接" if status.get("faulted") else
            "接收器不可用或震动转发未启用" if not self._can_start else "可开始限时测试 · 板端到时停止")
        live=bool(fresh and (connected or self.demo))
        counts=f"游戏命令 {status.get('received','—')} · USB 已完成 {status.get('sent','—')} · 错误 {status.get('errors','—')}"
        if not status:
            detail="震动状态尚未读取"
        elif not live:
            detail="最近一次状态："+counts+"\n当前马达强度与传输状态未知"
        else:
            left=round(status.get("left",0)*100/255);right=round(status.get("right",0)*100/255)
            transmission=" · ".join(word for key,word in (("pending","待发送"),("in_flight","传输中")) if status.get(key)) or "传输空闲"
            detail=f"左马达 {left}% · 右马达 {right}%\n{counts}\n{transmission}"
        self.rumble_detail.setText(detail)
        self.rumble_detail.setToolTip("\n".join(f"{key}={status.get(key,'—')}" for key in
            ("received","sent","errors","left","right","pending","in_flight","enabled","available","faulted","testing","remaining_ms")))

    def start_rumble(self):
        if self._can_start:
            left=round(self.left_spin.value()*255/100);right=round(self.right_spin.value()*255/100)
            self.command_requested.emit(f"RUMBLE TEST {left} {right} {self.duration_spin.value()}")

    def stop_rumble(self):
        if self._can_stop:self.command_requested.emit("RUMBLE STOP")


class FirmwareUpdatePage(QWidget):
    upgrade_requested=Signal(str,bool)
    STAGES={"validating":"校验固件", "entering_bootsel":"请求进入 BOOTSEL", "waiting_drive":"等待下载盘",
            "copying":"正在写入 UF2 · 请保持连接", "waiting_reconnect":"等待同一设备重连",
            "restoring":"读取设备实际状态", "complete":"升级完成 · 设备已重连", "failed":"升级失败", "cancelled":"升级已取消"}

    def __init__(self,demo=False):
        super().__init__();self.demo=demo;self.validated_path=None;self.busy=False
        self._connected=self._fresh=False;self._capabilities={}
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,10);layout.setSpacing(14)
        file,box=panel("桥接固件升级", "校验 RP2350 ARM-S UF2 · 保留设备配置区")
        row=QHBoxLayout();self.file_label=text_label("尚未选择固件文件")
        row.addWidget(self.file_label,1);self.choose_button=QPushButton("选择 UF2 文件…")
        self.choose_button.clicked.connect(self.choose_file);row.addWidget(self.choose_button);box.addLayout(row)
        self.image_info=text_label("选择本项目桥接版 UF2 后显示块数、地址范围与 SHA-256。");box.addWidget(self.image_info)
        self.validation_label=text_label("仅接受完整、无重叠且避开配置保留区的合法镜像。");box.addWidget(self.validation_label)
        layout.addWidget(file)
        flow,box=panel("升级与恢复", "写入完成并读取同一串口设备后，才报告升级成功")
        self.guidance=text_label("");box.addWidget(self.guidance)
        actions=QHBoxLayout();self.upgrade_button=QPushButton("开始自动升级");self.upgrade_button.setObjectName("primary")
        self.manual_button=QPushButton("已手动进入下载模式，开始写入")
        self.upgrade_button.clicked.connect(self.start_upgrade);self.manual_button.clicked.connect(self.start_manual)
        actions.addWidget(self.upgrade_button);actions.addWidget(self.manual_button);actions.addStretch();box.addLayout(actions)
        self.stage_label=text_label("等待选择固件","sectionTitle");box.addWidget(self.stage_label)
        self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setTextVisible(False);box.addWidget(self.progress)
        self.status_label=text_label("升级期间暂停调参和测试；未应用草稿不会自动保存。");box.addWidget(self.status_label)
        layout.addWidget(flow)
        self.version_label=text_label("设备实际版本：待读取");layout.addWidget(self.version_label)
        layout.addWidget(text_label("写入阶段请勿拔线或断电。成功表示 UF2 传输完成并恢复连接，不代表逐字节 Flash 回读。"))
        layout.addStretch();self.set_context(False,False,{})

    def choose_file(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,"选择桥接固件 UF2","","UF2 固件 (*.uf2)")
        if path:self.select_file(path)

    def select_file(self,path):
        if self.busy:return False
        self.validated_path=None
        try:
            try:from .firmware_update import FirmwareUpdater
            except ImportError:from firmware_update import FirmwareUpdater
            image=FirmwareUpdater().prepare(path)
        except (OSError,ValueError) as exc:
            self.validation_label.setText("校验失败："+str(exc));self.file_label.setText(str(path))
            self.image_info.setText("请重新选择本项目合法 UF2 镜像。");self._update_buttons();return False
        self.validated_path=str(path);self.file_label.setText(Path(path).name)
        self.image_info.setText(f"{image.blocks} 个 UF2 块  ·  0x{image.start_address:08X}–0x{image.end_address:08X}（末地址不含）\nSHA-256  {image.sha256}")
        self.validation_label.setText("✓ 校验通过 · 家族、块序号、地址与配置保留区检查完成")
        self._update_buttons();return True

    def set_context(self,connected,fresh,capabilities,version=None):
        self._connected,self._fresh,self._capabilities=connected,fresh,capabilities
        self.guidance.setText("演示模式 · 可预览文件校验，不会烧录设备。" if self.demo else
            "支持自动 BOOTSEL：选择 UF2，点击开始后等待设备重新连接。" if capabilities.get("bootsel") else
            "首次升级 / 旧固件：先连接一次设备以记录身份；按住板上 BOOT，重新插入 USB，出现 RP2350 下载盘后点击手动写入。只允许唯一匹配盘。")
        if version:self.version_label.setText("设备实际版本："+str(version))
        self._update_buttons()

    def _update_buttons(self):
        ready=bool(self.validated_path and not self.demo and not self.busy)
        self.upgrade_button.setEnabled(ready and self._connected and self._fresh and bool(self._capabilities.get("bootsel")))
        self.manual_button.setEnabled(ready);self.choose_button.setEnabled(not self.busy)

    def start_upgrade(self):
        if self.upgrade_button.isEnabled():self.upgrade_requested.emit(self.validated_path,False)

    def start_manual(self):
        if self.manual_button.isEnabled():self.upgrade_requested.emit(self.validated_path,True)

    def update_upgrade(self,state):
        self.busy=bool(state.get("busy"));stage=state.get("stage","")
        self.stage_label.setText(self.STAGES.get(stage,stage or "等待升级"))
        self.progress.setValue(max(0,min(100,int(state.get("progress",0)))))
        error=state.get("error")
        self.status_label.setText((str(error)+"\n恢复：按住 BOOT 重新插入 USB，选择合法 UF2 后使用手动写入。") if error else str(state.get("detail") or "请保持连接，等待当前阶段完成。"))
        self._update_buttons()
