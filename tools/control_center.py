"""RP2350 control center. Serial ownership belongs exclusively to Session.

Run ``python -m tools.control_center`` or use ``--demo`` for labelled synthetic
input. ``--demo --screenshot PATH`` captures a review image without hardware.
"""
import argparse
import copy
import math
import os
from pathlib import Path
import sys
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QProgressBar, QScrollArea, QSizePolicy, QSpinBox, QTabWidget, QVBoxLayout, QWidget)
try:
    from .control_widgets import BUTTONS, BITS, ControllerView, CurvePlot, PedalGauge, StickView
except ImportError:
    from control_widgets import BUTTONS, BITS, ControllerView, CurvePlot, PedalGauge, StickView


STYLE = """
QMainWindow, QWidget { background:#0c1220; color:#e4ecfa; font-family:'Microsoft YaHei UI'; font-size:12px; }
QLabel { background:transparent; }
QLabel#brand { font-size:24px; font-weight:700; letter-spacing:1px; }
QLabel#eyebrow { color:#43ddbd; font-size:10px; letter-spacing:2px; }
QLabel#muted { color:#8390a7; }
QLabel#sectionTitle { font-size:16px; font-weight:600; }
QLabel#notice { background:#152337; border-radius:7px; padding:9px 12px; color:#a9b9d2; }
QLabel#badge { border:1px solid #35425b; border-radius:11px; padding:5px 12px; color:#a9b9d2; }
QLabel#bindingSource { border:1px solid transparent; border-radius:5px; padding:6px; }
QLabel#bindingSource[pressed="true"] { border-color:#347e70; background:#173b36; color:#62efd0; font-weight:700; }
QFrame#card { background:#131d2e; border:1px solid #253047; border-radius:12px; }
QFrame#card QWidget { background:transparent; }
QFrame#footer { background:#101a2a; border-top:1px solid #253047; }
QPushButton { border:1px solid #35425b; border-radius:6px; padding:8px 15px; background:#1b2940; color:#d9e5f8; }
QPushButton:hover { background:#263852; border-color:#657697; }
QPushButton:pressed { background:#314660; }
QPushButton:disabled { color:#54617a; border-color:#273247; background:#151f30; }
QPushButton#primary { background:#43ddbd; color:#0a2421; border-color:#43ddbd; font-weight:700; }
QPushButton#primary:hover { background:#75efd5; }
QPushButton#primary:disabled { color:#52756d; background:#1c433f; border-color:#1c433f; }
QPushButton#save { border-color:#7b70c4; color:#c4bbff; }
QComboBox, QDoubleSpinBox, QSpinBox { background:#0e1727; border:1px solid #35425b; border-radius:5px; padding:6px 9px; min-height:20px; selection-background-color:#347e76; }
QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled { color:#5c6880; border-color:#273247; }
QComboBox QAbstractItemView { background:#17243a; selection-background-color:#31586a; color:#e4ecfa; }
QComboBox::drop-down { border:0; width:20px; }
QTabWidget::pane { border:0; }
QTabBar::tab { color:#8291aa; padding:12px 23px; margin:0 5px 10px 0; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#53e1c5; border-bottom:2px solid #43ddbd; }
QTabBar::tab:hover { color:#dfe9fa; }
QProgressBar { border:0; border-radius:3px; background:#29344a; min-height:6px; max-height:6px; }
QProgressBar::chunk { background:#9f91ff; border-radius:3px; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:#101827; width:8px; margin:0; }
QScrollBar::handle:vertical { background:#34435c; min-height:32px; border-radius:4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QToolTip { background:#24344c; color:#e4ecfa; border:1px solid #465875; padding:5px; }
"""


def label(text, name=None):
    widget = QLabel(text)
    if name: widget.setObjectName(name)
    return widget


def card(title=None, subtitle=None):
    frame = QFrame(); frame.setObjectName("card")
    layout = QVBoxLayout(frame); layout.setContentsMargins(20, 17, 20, 17); layout.setSpacing(10)
    if title: layout.addWidget(label(title, "sectionTitle"))
    if subtitle:
        sub = label(subtitle, "muted"); sub.setWordWrap(True); layout.addWidget(sub)
    return frame, layout


def scroll_page(widget):
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return scroll


def keyboard_names():
    names = {i+4: chr(65+i) for i in range(26)}
    names.update({i+30: str((i+1)%10) for i in range(10)})
    names.update({40:"Enter 回车",41:"Esc 退出",42:"Backspace 退格",43:"Tab",44:"Space 空格",
                  45:"-",46:"=",47:"[",48:"]",49:"\\",51:";",52:"'",53:"`",54:",",55:".",56:"/",
                  57:"Caps Lock",70:"Print Screen",71:"Scroll Lock",72:"Pause",73:"Insert",74:"Home",
                  75:"Page Up",76:"Delete",77:"End",78:"Page Down",79:"→ 右",80:"← 左",81:"↓ 下",82:"↑ 上",
                  83:"Num Lock",84:"小键盘 /",85:"小键盘 *",86:"小键盘 -",87:"小键盘 +",88:"小键盘 Enter",
                  0xE0:"左 Ctrl",0xE1:"左 Shift",0xE2:"左 Alt",0xE3:"左 Win",
                  0xE4:"右 Ctrl",0xE5:"右 Shift",0xE6:"右 Alt",0xE7:"右 Win"})
    names.update({58+i:f"F{i+1}" for i in range(12)})
    names.update({89+i:f"小键盘 {(i+1)%10}" for i in range(10)})
    return [(names.get(i, f"HID 0x{i:02X}"),i) for i in range(4,0xE8)]


class ControlCenter(QMainWindow):
    def __init__(self, session=None, demo=False):
        super().__init__()
        # Windows' offscreen plugin exposes no system fonts; load installed
        # faces explicitly so automated screenshots are as readable as desktop UI.
        if not QFontDatabase.families() and sys.platform=="win32":
            fonts=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"
            for face in ("msyh.ttc","msyhbd.ttc","segoeui.ttf","seguisb.ttf"):
                if (fonts/face).exists():QFontDatabase.addApplicationFont(str(fonts/face))
        self.demo, self.session = demo, session
        self.connected, self.dirty = False, False
        self._loading, self._revision, self._pending_revision = False, 0, None
        self._pending_save, self._saved, self._applied_changed = False, False, False
        self._baseline, self._latest, self._has_profile = None, {}, False
        self._persistent_config = None
        self._last_snapshot = None
        self.pedal_editors, self.stick_editors, self.trigger_editors, self.binding_editors = [], [], [], []
        self.pedal_plots, self.stick_plots, self.trigger_plots = [], [], []
        self.calibration_buttons, self.pedal_details = [], []
        self.binding_source_labels = []
        self.setWindowTitle("RP2350 · 控制中心" + (" · 演示模式" if demo else ""))
        self.resize(1280,800); self.setMinimumSize(900,650); self.setStyleSheet(STYLE)
        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(26,20,26,0); outer.setSpacing(13)
        head = QHBoxLayout(); brand = QVBoxLayout(); brand.setSpacing(3)
        brand.addWidget(label("RP2350  /  CONTROL CENTER", "eyebrow"))
        brand.addWidget(label("驾驶控制中心", "brand")); head.addLayout(brand); head.addStretch()
        self.connection_label = label("● 未连接设备", "badge"); head.addWidget(self.connection_label)
        self.port_combo = QComboBox(); self.port_combo.setMinimumWidth(200)
        self.port_combo.addItem("自动发现 RP2350 设备", ""); head.addWidget(self.port_combo)
        self.connect_button = QPushButton("连接设备"); self.connect_button.clicked.connect(self.toggle_connection)
        head.addWidget(self.connect_button); outer.addLayout(head)
        self.notice_label = label("演示模式 · 所有输入为模拟数据，未连接硬件；参数仅作本地预览。" if demo else
                                  "连接 Type-C 串口后读取设备。参数应用到 RAM，保存到 Flash 后才能断电保留。", "notice")
        self.notice_label.setWordWrap(True); outer.addWidget(self.notice_label)
        self.tabs = QTabWidget(); outer.addWidget(self.tabs,1)
        self.tabs.addTab(self._dashboard(), "概览")
        self.tabs.addTab(self._pedals_page(), "踏板调校")
        self.tabs.addTab(self._sticks_page(), "摇杆与扳机")
        self.tabs.addTab(self._bindings_page(), "按键映射")
        footer = QFrame(); footer.setObjectName("footer"); footer.setMinimumHeight(75)
        foot = QHBoxLayout(footer); foot.setContentsMargins(15,13,15,13)
        state = QVBoxLayout(); state.setSpacing(4)
        self.edit_label = label("等待读取设备参数"); self.persistence_label = label("Flash 状态未知", "muted")
        state.addWidget(self.edit_label); state.addWidget(self.persistence_label); foot.addLayout(state); foot.addStretch()
        self.revert_button = QPushButton("撤销修改"); self.revert_button.clicked.connect(self.revert_changes)
        self.apply_button = QPushButton("应用到设备"); self.apply_button.setObjectName("primary"); self.apply_button.clicked.connect(self.apply_changes)
        self.save_button = QPushButton("保存到 Flash"); self.save_button.setObjectName("save"); self.save_button.clicked.connect(self.save_changes)
        self.save_button.setToolTip("先应用修改，结束校准、松开踏板和手柄，等待回零后保存。仅收到设备成功确认后显示已保存。")
        for b in (self.revert_button,self.apply_button,self.save_button): foot.addWidget(b)
        outer.addWidget(footer)
        self._watchdog=QTimer(self);self._watchdog.setInterval(100)
        self._watchdog.timeout.connect(self._watchdog_tick);self._watchdog.start()
        if session:
            session.ports_changed.connect(self.on_ports)
            session.connected_changed.connect(self.on_connected)
            session.snapshot.connect(self.on_snapshot)
            session.message.connect(self.on_message)
            session.start()
        if demo:
            self.port_combo.setEnabled(False); self.connect_button.setEnabled(False)
            self._demo_timer = QTimer(self); self._demo_timer.timeout.connect(self._demo_tick)
            self._demo_t = 0.; self._demo_tick(); self._demo_timer.start(50)
        self._update_state()

    def _dashboard(self):
        page=QWidget(); layout=QHBoxLayout(page); layout.setContentsMargins(0,0,0,10); layout.setSpacing(16)
        left=QVBoxLayout(); left.setSpacing(14); layout.addLayout(left,1)
        pedal_card,pl=card("踏板输出", "设备实际输出 · 独立 16-bit 踏板采样")
        gauges=QHBoxLayout(); self.gauges=[PedalGauge("油门 · RT","#43ddbd"),PedalGauge("刹车 · LT","#9f91ff")]
        for g in self.gauges: gauges.addWidget(g)
        pl.addLayout(gauges,1)
        self.pedal_summary=label("原始值 —    滤波值 —", "muted"); self.pedal_summary.setWordWrap(True); pl.addWidget(self.pedal_summary)
        left.addWidget(pedal_card,3)
        status,sl=card("设备状态")
        self.device_state=label("等待连接", "sectionTitle"); sl.addWidget(self.device_state)
        self.device_detail=label("踏板校准、输出使能与固件能力将在连接后显示。", "muted"); self.device_detail.setWordWrap(True); sl.addWidget(self.device_detail)
        self.keyboard_status=label("键盘输出 —", "muted"); self.keyboard_status.setWordWrap(True); sl.addWidget(self.keyboard_status)
        sl.addStretch(); left.addWidget(status,2)
        host,hl=card("手柄输入监视", "USB Host → 曲线与映射 → MAX 踏板合并 → 电脑")
        source=QHBoxLayout(); source.addWidget(label("观察数据层", "muted")); self.source_combo=QComboBox()
        for title,key in (("原始输入 · Raw","raw"),("变换后 · Processed","processed"),("最终输出 · Output","output")): self.source_combo.addItem(title,key)
        self.source_combo.setCurrentIndex(2); self.source_combo.currentIndexChanged.connect(self._render_live)
        source.addWidget(self.source_combo); source.addStretch(); hl.addLayout(source)
        self.controller=ControllerView(); hl.addWidget(self.controller,3)
        axes=QHBoxLayout(); self.live_sticks=[]
        for title in ("左摇杆","右摇杆"):
            col=QVBoxLayout(); col.addWidget(label(title,"muted"),0,Qt.AlignCenter); view=StickView(); view.setMaximumHeight(120); col.addWidget(view)
            self.live_sticks.append(view); axes.addLayout(col)
        triggerbox=QVBoxLayout(); self.live_triggers=[]
        for name in ("LT","RT"):
            text=label(name+"  —","muted"); bar=QProgressBar(); bar.setRange(0,255); bar.setTextVisible(False)
            triggerbox.addWidget(text); triggerbox.addWidget(bar); self.live_triggers.append((text,bar))
        triggerbox.addStretch(); axes.addLayout(triggerbox); hl.addLayout(axes,2)
        self.host_status=label("手柄遥测 — 未连接", "muted"); self.host_status.setWordWrap(True); hl.addWidget(self.host_status)
        layout.addWidget(host,1)
        return page

    def _spin(self, lo, hi, initial, suffix="", integer=False):
        spin=QSpinBox() if integer else QDoubleSpinBox()
        spin.setRange(lo,hi); spin.setValue(initial); spin.setSuffix(suffix)
        if not integer: spin.setDecimals(2); spin.setSingleStep(.1)
        spin.valueChanged.connect(self._edited)
        return spin

    def _pedals_page(self):
        page=QWidget(); box=QVBoxLayout(page); box.setContentsMargins(0,0,0,10)
        row=QHBoxLayout(); row.addWidget(label("输出模式", "muted")); self.mode_combo=QComboBox()
        self.mode_combo.addItem("原生 XInput 手柄", "JOYSTICK"); self.mode_combo.addItem("键盘 W / S", "KEYBOARD")
        self.mode_combo.setToolTip("输出模式仅在当前 RAM 会话生效；重启恢复 JOYSTICK。保存到 Flash 保存调校参数，不保存输出模式。")
        self.mode_combo.currentIndexChanged.connect(self._edited); row.addWidget(self.mode_combo); row.addStretch()
        row.addWidget(label("本地预览 → 应用到 RAM → 保存到 Flash", "muted")); box.addLayout(row)
        cards=QHBoxLayout(); cards.setSpacing(16); box.addLayout(cards)
        for i,(title,color) in enumerate((("油门 · GP26 / RT","#43ddbd"),("刹车 · GP27 / LT","#9f91ff"))):
            frame,layout=card(title,"校准行程、释放迟滞与响应曲线")
            plot=CurvePlot(color); plot.setMinimumHeight(145); self.pedal_plots.append(plot); layout.addWidget(plot)
            form=QGridLayout(); form.setSpacing(8)
            edits={"on":self._spin(.01,50,3," %"),"off":self._spin(0,49.99,1," %"),
                   "gamma":self._spin(1,4,1 if i==0 else 2," γ"),"window":self._spin(1,8,4," 点",True)}
            for j,(key,title2) in enumerate((("on","触发阈值"),("off","释放阈值"),("gamma","响应曲线"),("window","滤波窗口"))):
                form.addWidget(label(title2),j//2,(j%2)*2); form.addWidget(edits[key],j//2,(j%2)*2+1)
            self.pedal_editors.append(edits); layout.addLayout(form)
            detail=label("未读取校准数据", "muted"); detail.setWordWrap(True); layout.addWidget(detail); self.pedal_details.append(detail)
            calhead=QHBoxLayout(); calhead.addWidget(label("行程校准", "sectionTitle")); calhead.addStretch()
            cancel=QPushButton("取消校准"); cancel.clicked.connect(lambda checked=False,j=i:self._command(f"CAL {j} CANCEL")); calhead.addWidget(cancel); self.calibration_buttons.append(cancel)
            layout.addLayout(calhead); calrow=QHBoxLayout()
            for text,command in (("① 全松开 · 开始",f"CAL {i} BEGIN"),("② 踩到底保持 · 完成",f"CAL {i} END")):
                btn=QPushButton(text); btn.clicked.connect(lambda checked=False,c=command:self._command(c)); calrow.addWidget(btn); self.calibration_buttons.append(btn)
            layout.addLayout(calrow)
            cards.addWidget(frame)
        note=label("曲线显示启用后的响应；触发阈值决定开始输出，释放阈值决定回零，二者之间保留迟滞。校准完成后松开双踏板等待回零，再保存。", "muted")
        note.setWordWrap(True); box.addWidget(note); box.addStretch()
        return scroll_page(page)

    def _sticks_page(self):
        page=QWidget(); grid=QGridLayout(page); grid.setContentsMargins(0,0,0,10); grid.setSpacing(14)
        self.profile_notice=label("连接支持 PROFILE 的固件后可调节摇杆与扳机。", "muted")
        grid.addWidget(self.profile_notice,0,0,1,2)
        for i in range(2):
            frame,lay=card(("左摇杆 · LX / LY","右摇杆 · RX / RY")[i],"径向死区 · 保留方向 · 设备端处理")
            plot=CurvePlot("#9f91ff"); plot.setMinimumHeight(125); self.stick_plots.append(plot); lay.addWidget(plot)
            form=QGridLayout(); edits={"deadzone":self._spin(0,95,0," %"),"gamma":self._spin(1,4,1," γ"),"invert":QComboBox()}
            for text,value in (("不反转",0),("反转 X",1),("反转 Y",2),("反转 X + Y",3)): edits["invert"].addItem(text,value)
            edits["invert"].currentIndexChanged.connect(self._edited)
            for j,(key,text) in enumerate((("deadzone","中心死区"),("gamma","响应曲线"))):
                form.addWidget(label(text),0,j*2);form.addWidget(edits[key],0,j*2+1)
            form.addWidget(label("轴向反转"),1,0);form.addWidget(edits["invert"],1,1,1,3)
            self.stick_editors.append(edits); lay.addLayout(form); grid.addWidget(frame,1,i)
        for i in range(2):
            frame,lay=card(("左扳机 · LT","右扳机 · RT")[i])
            plot=CurvePlot("#43ddbd"); plot.setMinimumHeight(110); self.trigger_plots.append(plot)
            h=QHBoxLayout(); h.addWidget(plot,1); form=QFormLayout()
            edits={"deadzone":self._spin(0,95,0," %"),"gamma":self._spin(1,4,1," γ")}
            for key,text in (("deadzone","起始死区"),("gamma","响应曲线")):form.addRow(text,edits[key])
            self.trigger_editors.append(edits); h.addLayout(form); lay.addLayout(h); grid.addWidget(frame,2,i)
        grid.setRowStretch(3,1); return scroll_page(page)

    def _bindings_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,10)
        intro=label("将 14 个实体按键映射为手柄按钮、单个键盘按键或禁用。所有映射由设备执行，关闭控制中心后仍生效。", "muted")
        intro.setWordWrap(True); layout.addWidget(intro)
        frame,lay=card(); grid=QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(6)
        for offset in (0,4):
            for col,text in enumerate(("来源按键","输出类型","目标")):grid.addWidget(label(text,"muted"),0,offset+col)
        for i,name in enumerate(BUTTONS):
            row,col=i%7+1,(i//7)*4
            source=label(name,"bindingSource"); source.setMinimumWidth(55)
            source.setProperty("pressed",False); source.setToolTip("实体来源按键 · 实时高亮原始输入")
            self.binding_source_labels.append(source); grid.addWidget(source,row,col)
            kind=QComboBox()
            for text,value in (("手柄按钮",0),("键盘按键",1),("禁用",2)):kind.addItem(text,value)
            target=QComboBox(); target.setMinimumWidth(145)
            self.binding_editors.append((kind,target)); self._populate_target(i,0,i)
            kind.currentIndexChanged.connect(lambda index,j=i:self._binding_kind_changed(j))
            target.currentIndexChanged.connect(self._edited)
            grid.addWidget(kind,row,col+1); grid.addWidget(target,row,col+2)
        grid.setColumnMinimumWidth(3,30); lay.addLayout(grid); layout.addWidget(frame)
        note=label("支持左右 Ctrl / Shift / Alt / Win。多个来源可指向同一目标；键盘最多同时发送 6 个普通按键，修饰键独立。遥测面板可查看最终键盘报告。", "muted")
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch(); return scroll_page(page)

    def _populate_target(self,index,kind,value=None):
        target=self.binding_editors[index][1]; target.blockSignals(True); target.clear()
        choices=list(zip(BUTTONS,range(14))) if kind==0 else keyboard_names() if kind==1 else [("无输出",0)]
        for text,data in choices:target.addItem(text,data)
        if value is not None:target.setCurrentIndex(max(0,target.findData(value)))
        target.setEnabled(kind!=2 and self._has_profile); target.blockSignals(False)

    def _binding_kind_changed(self,index):
        self._populate_target(index,self.binding_editors[index][0].currentData()); self._edited()

    def _edited(self,*args):
        if self._loading:return
        self._revision+=1
        self.dirty=self._baseline is not None and self._preview()!=self._baseline
        self._update_curves(); self._update_state()

    def _preview(self):
        result={"mode":self.mode_combo.currentData(),"axes":[]}
        for edits in self.pedal_editors:
            result["axes"].append({key:int(round(widget.value()*(1 if key=="window" else 100))) for key,widget in edits.items()})
        if self._has_profile:
            result["profile"]={"sticks":[],"triggers":[],"bindings":[]}
            for name,editors in (("sticks",self.stick_editors),("triggers",self.trigger_editors)):
                for edits in editors:
                    result["profile"][name].append({key:widget.currentData() if key=="invert" else int(round(widget.value()*100)) for key,widget in edits.items()})
            result["profile"]["bindings"]=[[kind.currentData(),target.currentData() or 0] for kind,target in self.binding_editors]
        return result

    def _config_from_snapshot(self,data):
        pedal=data["pedal"]
        config={"mode":pedal.get("mode","JOYSTICK"),"axes":[{k:axis[k] for k in ("on","off","gamma","window")} for axis in pedal["axes"]]}
        if data.get("profile"):config["profile"]=copy.deepcopy(data["profile"])
        return config

    def _load_config(self,config):
        self._loading=True
        self.mode_combo.setCurrentIndex(max(0,self.mode_combo.findData(config["mode"])))
        for edits,values in zip(self.pedal_editors,config["axes"]):
            for key,widget in edits.items():widget.setValue(values[key]/(1 if key=="window" else 100))
        profile=config.get("profile")
        if profile:
            for name,editors in (("sticks",self.stick_editors),("triggers",self.trigger_editors)):
                for edits,values in zip(editors,profile[name]):
                    for key,widget in edits.items():
                        if key=="invert":widget.setCurrentIndex(max(0,widget.findData(values[key])))
                        else:widget.setValue(values[key]/100)
            for i,(kind,target) in enumerate(profile["bindings"]):
                combo=self.binding_editors[i][0]; combo.setCurrentIndex(max(0,combo.findData(kind))); self._populate_target(i,kind,target)
        self._loading=False; self._update_curves()

    def _update_curves(self):
        for edits,plot in zip(self.pedal_editors,self.pedal_plots):
            plot.hysteresis_on=round(edits["on"].value()*100)
            plot.set_curve(round(edits["off"].value()*100),round(edits["gamma"].value()*100))
        for editors,plots in ((self.stick_editors,self.stick_plots),(self.trigger_editors,self.trigger_plots)):
            for edits,plot in zip(editors,plots):plot.set_curve(round(edits["deadzone"].value()*100),round(edits["gamma"].value()*100))

    def on_ports(self,ports):
        current=self.port_combo.currentData(); self.port_combo.clear()
        for port in ports:
            device=port.get("device",""); serial=port.get("serial_number") or ""
            suffix=f" · {serial[-6:]}" if serial else ""
            self.port_combo.addItem(f"{device} · {port.get('description','RP2350')}{suffix}",device)
            self.port_combo.setItemData(self.port_combo.count()-1,
                f"{device}\n{port.get('description','RP2350')}\n序列号：{serial or '未提供'}",Qt.ToolTipRole)
        if not ports:self.port_combo.addItem("未发现 RP2350 设备","")
        found=self.port_combo.findData(current)
        if found>=0:self.port_combo.setCurrentIndex(found)

    def toggle_connection(self):
        if not self.session:return
        if self.connected:self.session.disconnect_port()
        elif self.port_combo.currentData():self.session.connect_port(self.port_combo.currentData())
        else:self.on_message("未发现设备；检查 Type-C 连接与驱动，等待自动扫描。",True)

    def on_connected(self,connected,description):
        if connected:
            # Every successful open is a new Session epoch; an older False
            # event may have been discarded. Never carry drafts across boards.
            discarded=self.dirty
            self._baseline=None;self._persistent_config=None;self._latest={};self._last_snapshot=None
            self.dirty=False;self._saved=False;self._applied_changed=False
            self._pending_revision=None;self._pending_save=False;self._revision+=1
            self._has_profile=False
            for editors in (self.stick_editors,self.trigger_editors):
                for edits in editors:
                    for widget in edits.values():widget.setEnabled(False)
            for kind,target in self.binding_editors:kind.setEnabled(False);target.setEnabled(False)
            self.notice_label.setText("新连接已建立；已丢弃离线未应用草稿，已应用的设备参数不会丢失。正在读取当前设备。" if discarded else
                                      "新连接已建立，正在读取当前设备参数；读取完成前禁止写入。")
            self.notice_label.setStyleSheet("")
        self.connected=connected
        self.connection_label.setText(("● 已连接 · " if connected else "○ 未连接 · ")+description)
        self.connection_label.setStyleSheet("color:#43ddbd;border-color:#27675d;" if connected else "")
        self.connect_button.setText("断开连接" if connected else "连接设备")
        if not connected:
            self._pending_revision=None; self._pending_save=False
            self._saved=False
        self._render_live(); self._update_state()

    def on_snapshot(self,data):
        self._last_snapshot=time.monotonic()
        self._latest=data
        has_profile=bool(data.get("profile")); self._has_profile=has_profile
        for editors in (self.stick_editors,self.trigger_editors):
            for edits in editors:
                for widget in edits.values():widget.setEnabled(has_profile)
        for kind,target in self.binding_editors:
            kind.setEnabled(has_profile); target.setEnabled(has_profile and kind.currentData()!=2)
        self.profile_notice.setText("设备端径向死区与响应曲线 · 显示预览不会改变输出，应用后生效。" if has_profile else "当前固件不支持 PROFILE：可使用踏板功能；摇杆、扳机与映射不可用。")
        if data.get("pedal",{}).get("axes") and (self._baseline is None or data.get("refresh_config")):
            # Calibration endpoints/flags are board-side settings, not local
            # editors. Track the complete persistent record independently so
            # CAL END invalidates a previous SAVE without creating fake edits.
            persistent={"mode":data["pedal"].get("mode","JOYSTICK"),
                        "axes":copy.deepcopy(data["pedal"]["axes"]),
                        "profile":copy.deepcopy(data.get("profile"))}
            if self._persistent_config is not None and persistent!=self._persistent_config:
                self._saved=False;self._applied_changed=True
            self._persistent_config=persistent
            previous=self._baseline
            self._baseline=self._config_from_snapshot(data)
            if previous is not None and previous!=self._baseline:
                self._saved=False;self._applied_changed=True
            if self._pending_revision is not None:
                if self._revision==self._pending_revision:self._load_config(self._baseline)
                self._pending_revision=None; self._applied_changed=True; self._saved=False
            elif not self.dirty:self._load_config(self._baseline)
            if previous is None:self._load_config(self._baseline)
            self.dirty=self._preview()!=self._baseline
        if data.get("saved"):
            self._saved=True; self._pending_save=False; self._applied_changed=False
        self._render_live(); self._update_state()

    def _snapshot_age(self):
        return max(0.0,time.monotonic()-self._last_snapshot) if self._last_snapshot is not None else float("inf")

    def _data_fresh(self):
        return self._last_snapshot is not None and self._snapshot_age()<=.5

    def _watchdog_tick(self):
        self._render_live();self._update_state()

    def _render_live(self,*args):
        if not hasattr(self,"host_status"):return
        pedal=self._latest.get("pedal",{}); telemetry=self._latest.get("telemetry")
        stale=(self.connected or self.demo) and self._last_snapshot is not None and not self._data_fresh()
        live=(self.connected or self.demo) and bool(pedal) and self._data_fresh()
        for i,gauge in enumerate(self.gauges):gauge.set_value((pedal.get("output",[0,0])[i]/65535)*100,live)
        if live:
            self.pedal_summary.setText("油门  原始 {} / 滤波 {}      刹车  原始 {} / 滤波 {}".format(*[pedal.get(k,[0,0])[i] for i in (0,1) for k in ("raw","filtered")]))
            cal=pedal.get("calibration_axis",-1)
            blocked=bool(telemetry and telemetry.get("blocked"))
            self.device_state.setText("模拟设备 · 演示输入" if self.demo else "校准进行中" if cal>=0 else "等待手柄回零 · 输出已阻止" if blocked else "输出已使能" if pedal.get("armed") else "等待回零使能")
            detail=f"模式 {pedal.get('mode','—')}  ·  {'校准轴 '+str(cal) if cal>=0 else '未在校准'}\n{'支持控制配置与遥测' if self._has_profile else '兼容模式 · 仅踏板调校'}"
            if blocked:detail+="\n松开踏板，将手柄摇杆、扳机与按键回零，等待恢复输出。"
            self.device_detail.setText(detail)
            for i,(details,plot) in enumerate(zip(self.pedal_details,self.pedal_plots)):
                axis=pedal.get("axes",[{},{}])[i]; released=axis.get("released",0); pressed=axis.get("pressed",4095)
                t=(pedal.get("filtered",[0,0])[i]-released)/(pressed-released) if pressed!=released else 0
                plot.set_cursor(t,True)
                details.setText(f"{'已校准' if axis.get('calibrated') else '尚未校准'} · 松开 {released} / 踩下 {pressed}\n原始 {pedal.get('raw',[0,0])[i]} · 滤波 {pedal.get('filtered',[0,0])[i]}")
        else:
            self.pedal_summary.setText("原始值 —    滤波值 —    输出 —")
            self.device_state.setText("数据已过期，等待串口回复" if stale else "已连接 · 正在读取设备" if self.connected else "设备未连接 · 读数无效")
            self.device_detail.setText("本地编辑已保留；恢复接收后自动更新，连接保持。" if stale else "等待当前设备的实际参数与实时输入。" if self.connected else "连接后读取实际参数与实时输入。")
            for plot in self.pedal_plots:plot.set_cursor(0,False)
        host_age=telemetry.get("age",0)+int(self._snapshot_age()*1000) if telemetry and self._last_snapshot is not None else 0
        fresh=live and bool(telemetry) and telemetry.get("state",0)==3 and host_age<=250
        # Host age describes the attached controller, not the CDC snapshot.
        # Final output is still current when only the two pedals are attached.
        valid=bool(live and telemetry) if self.source_combo.currentData()=="output" else fresh
        pad=telemetry.get(self.source_combo.currentData(),[0]*7) if telemetry else [0]*7
        if not isinstance(pad,(list,tuple)) or len(pad)<7:pad=[0]*7;valid=False
        self.controller.set_value(pad[0],valid)
        rawpad=telemetry.get("raw",[0]*7) if telemetry else [0]*7
        rawvalid=isinstance(rawpad,(list,tuple)) and len(rawpad)>=7
        if not rawvalid:rawpad=[0]*7
        for i,source in enumerate(self.binding_source_labels):
            pressed=bool(fresh and rawvalid and rawpad[0]&(1<<BITS[i]))
            if source.property("pressed")!=pressed:
                source.setProperty("pressed",pressed)
                source.style().unpolish(source);source.style().polish(source);source.update()
        for i,view in enumerate(self.live_sticks):
            view.set_value(pad[3+i*2],pad[4+i*2],valid)
            self.stick_plots[i].set_cursor(min(1,math.hypot(rawpad[3+i*2],rawpad[4+i*2])/32767),fresh and rawvalid)
        for i,(text,bar) in enumerate(self.live_triggers):
            text.setText(f"{('LT','RT')[i]}   {pad[1+i]/255*100:.1f}%" if valid else f"{('LT','RT')[i]}   —")
            bar.setValue(pad[1+i] if valid else 0); self.trigger_plots[i].set_cursor(rawpad[1+i]/255,fresh and rawvalid)
        if telemetry and live:
            states=("未接入","枚举中","握手中","输入活动","输入超时")
            st=telemetry.get("state",0); state=states[st] if 0<=st<len(states) else str(st)
            self.host_status.setText(f"{'模拟 Host' if self.demo else 'USB Host'} · {state} · 报告年龄 {host_age} ms\n报告 {telemetry.get('reports',0)} · 超时 {telemetry.get('timeouts',0)}"+(" · Host 读数无效" if not fresh else ""))
            keys=telemetry.get("keys",[0]*8)
            self.keyboard_status.setText("键盘 HID  "+" ".join(f"{v:02X}" for v in keys)+(" · 按键过多" if telemetry.get("keyboard_rollover") else "")+(" · 输出已阻止" if telemetry.get("blocked") else ""))
        else:
            self.host_status.setText("数据已过期，等待串口回复" if stale else "当前固件不支持手柄遥测" if live else "手柄遥测 — 未连接")
            self.keyboard_status.setText("键盘输出 — 遥测不可用")

    def _update_state(self):
        ready=self.connected and not self.demo and self._baseline is not None and self._data_fresh()
        stale=self.connected and self._last_snapshot is not None and not self._data_fresh()
        pending=self._pending_revision is not None or self._pending_save
        self.apply_button.setEnabled(ready and self.dirty and not pending)
        self.revert_button.setEnabled(self.dirty and not pending)
        self.save_button.setEnabled(ready and not self.dirty and not pending)
        for button in self.calibration_buttons:button.setEnabled(ready and not pending)
        self.edit_label.setText("演示模式 · 修改仅作预览" if self.demo else "数据已过期，等待串口回复 · 本地编辑已保留" if stale else "正在等待设备确认…" if pending else
                                "有未应用的修改 · 当前仅为本地预览" if self.dirty else "参数已应用到设备 RAM" if ready else
                                "已连接 · 等待读取当前设备参数" if self.connected else "离线 · 等待连接设备")
        self.edit_label.setStyleSheet("color:#f5cd75" if self.dirty else "color:#a9b9d2")
        self.persistence_label.setText("演示数据 · 不会写入设备" if self.demo else "Flash 已保存 · 设备已确认" if self._saved else
                                       "RAM 已修改 · 未保存到 Flash" if self._applied_changed else "Flash 状态未知 · 读取参数不代表已经保存")

    def apply_changes(self):
        if not self.connected or self.demo or not self._data_fresh() or self._baseline is None or not self.dirty or self._pending_revision is not None or self._pending_save:return
        current=self._preview(); commands=[]
        for i,axis in enumerate(current["axes"]):
            if not 0<=axis["off"]<axis["on"]<=5000:
                self.on_message("释放阈值必须小于触发阈值；请调整后应用。",True);return
            if axis!=self._baseline["axes"][i]:commands.append("SET {} {} {} {} {}".format(i,axis["on"],axis["off"],axis["gamma"],axis["window"]))
        if current["mode"]!=self._baseline["mode"]:commands.append("MODE "+current["mode"])
        if "profile" in current:
            for name,command,keys in (("sticks","STICK",("deadzone","gamma","invert")),("triggers","TRIGGER",("deadzone","gamma"))):
                for i,values in enumerate(current["profile"][name]):
                    if values!=self._baseline.get("profile",{}).get(name,[None,None])[i]:commands.append(f"{command} {i} "+" ".join(str(values[k]) for k in keys))
            for i,binding in enumerate(current["profile"]["bindings"]):
                if binding!=self._baseline["profile"]["bindings"][i]:commands.append(f"BIND {i} {binding[0]} {binding[1]}")
        if commands:
            self._saved=False;self._pending_revision=self._revision; self._update_state(); self.session.submit(commands)

    def revert_changes(self):
        if self._baseline:self._load_config(self._baseline);self.dirty=False;self._revision+=1;self._update_state()

    def save_changes(self):
        if not self.connected or self.demo or not self._data_fresh() or self._baseline is None or self.dirty or self._pending_save or self._pending_revision is not None:return
        self._pending_save=True;self._update_state();self.session.submit(["SAVE"])

    def _command(self,command):
        if self.connected and not self.demo and self._baseline is not None and self._data_fresh():self.session.submit([command])

    def on_message(self,text,error=False):
        if error:self._pending_revision=None;self._pending_save=False
        self.notice_label.setText(text)
        self.notice_label.setStyleSheet("color:#f5b5b7;background:#342432;" if error else "")
        self._update_state()

    def closeEvent(self,event):
        self._watchdog.stop()
        if hasattr(self,"_demo_timer"):self._demo_timer.stop()
        if self.session:self.session.close()
        super().closeEvent(event)

    def _demo_tick(self):
        self._demo_t+=.025; t=self._demo_t
        a=.36+.20*math.sin(t); b=.13+.12*math.sin(t*.8)
        axes=[{"released":280,"pressed":3650,"on":300,"off":100,"gamma":100+i*100,"window":4,"calibrated":True} for i in range(2)]
        raw=[int(280+3370*a),int(280+3370*b)]
        profile={"sticks":[{"deadzone":800,"gamma":130,"invert":0},{"deadzone":600,"gamma":100,"invert":0}],"triggers":[{"deadzone":300,"gamma":100} for _ in range(2)],"bindings":[[0,i] for i in range(14)]}
        pad=[(1<<12)|(1<<8),int(b*255),int(a*255),int(math.sin(t)*19000),int(math.cos(t)*13000),4000,-2500]
        self.connection_label.setText("DEMO · 演示模式 · 无硬件连接")
        self.on_snapshot({"refresh_config":self._baseline is None,"pedal":{"axes":axes,"mode":"JOYSTICK","armed":True,"calibration_axis":-1,"raw":raw,"filtered":[v-2 for v in raw],"output":[int(a*65535),int(b*b*65535)]},"profile":profile,"capabilities":{"profile":1,"telemetry":1},"telemetry":{"state":3,"age":12,"reports":int(t*400),"timeouts":0,"raw":pad,"processed":pad,"output":pad,"keys":[0]*8,"blocked":False}})


def main(argv=None):
    parser=argparse.ArgumentParser(description="RP2350 驾驶控制中心")
    parser.add_argument("--demo",action="store_true",help="明确标记的模拟数据；不连接硬件")
    parser.add_argument("--screenshot",type=Path,help="保存界面截图并退出（建议与 --demo 一起使用）")
    parser.add_argument("--tab",type=int,default=0,choices=range(4),help="截图/启动页面 0..3")
    args=parser.parse_args(argv)
    app=QApplication.instance() or QApplication(sys.argv[:1]); app.setFont(QFont("Microsoft YaHei UI",9))
    session=None
    if not args.demo:
        try:from .control_session import Session
        except ImportError:from control_session import Session
        session=Session()
    window=ControlCenter(session,demo=args.demo);window.tabs.setCurrentIndex(args.tab);window.show()
    if args.screenshot:
        def capture():
            args.screenshot.parent.mkdir(parents=True,exist_ok=True);window.grab().save(str(args.screenshot));window.close();app.quit()
        QTimer.singleShot(450,capture)
    return app.exec()


if __name__=="__main__":raise SystemExit(main())
