"""Painted Qt input visualizers. All values are explicit device/demo samples."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

MUTED = QColor("#8390a7")
GRID = QColor("#263246")
BUTTONS = ("↑", "↓", "←", "→", "START", "BACK", "LS", "RS", "LB", "RB", "A", "B", "X", "Y")
BITS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15)


def curve_value(x, deadzone=0, gamma=100):
    x = min(1.0, max(0.0, float(x)))
    dz = min(.95, max(0, deadzone / 10000))
    return max(0, (x - dz) / (1 - dz)) ** (gamma / 100)


class PedalGauge(QWidget):
    def __init__(self, title, color="#43ddbd", parent=None):
        super().__init__(parent)
        self.title, self.color, self.value, self.active = title, QColor(color), 0.0, False
        self.setMinimumSize(180, 150)

    def set_value(self, value, active=True):
        self.value = min(100, max(0, float(value)))
        self.active = active
        self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = min(w * .38, h * .72)
        center = QPointF(w / 2, h * .70)
        rect = QRectF(center.x() - r, center.y() - r, r * 2, r * 2)
        p.setPen(QPen(GRID, 11, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 25 * 16, 130 * 16)
        color = self.color if self.active else MUTED
        p.setPen(QPen(color, 11, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 155 * 16, -int(130 * 16 * self.value / 100))
        p.setPen(QColor("#edf4ff") if self.active else MUTED)
        font = QFont("Segoe UI", max(22, int(r * .40)), QFont.DemiBold); p.setFont(font)
        p.drawText(QRectF(0, center.y() - r * .68, w, r * .55), Qt.AlignCenter,
                   f"{self.value:.1f}%" if self.active else "—")
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.setPen(MUTED); p.drawText(QRectF(0, center.y() - r * .1, w, 28), Qt.AlignCenter, self.title)
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(center.x() - r - 4, center.y() - 5, 40, 20), Qt.AlignCenter, "0")
        p.drawText(QRectF(center.x() + r - 34, center.y() - 5, 40, 20), Qt.AlignCenter, "100")


class CurvePlot(QWidget):
    def __init__(self, color="#43ddbd", parent=None):
        super().__init__(parent)
        self.color, self.deadzone, self.gamma, self.cursor, self.active = QColor(color), 0, 100, 0.0, False
        self.hysteresis_on = None
        self.setMinimumSize(210, 145)
        self.setToolTip("本地曲线预览；点击应用后才由设备执行。圆点表示当前输入对应的预览输出。")

    def set_curve(self, deadzone, gamma):
        self.deadzone, self.gamma = deadzone, gamma; self.update()

    def set_cursor(self, value, active=True):
        self.cursor, self.active = min(1, max(0, value)), active; self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(32, 14, self.width() - 49, self.height() - 43)
        if self.hysteresis_on is not None:
            offx=rect.left()+rect.width()*self.deadzone/10000
            onx=rect.left()+rect.width()*self.hysteresis_on/10000
            shade=QColor(self.color); shade.setAlpha(30)
            p.fillRect(QRectF(offx,rect.top(),max(0,onx-offx),rect.height()),shade)
            p.setPen(QPen(self.color,1,Qt.DotLine));p.drawLine(QPointF(onx,rect.top()),QPointF(onx,rect.bottom()))
        for i in range(5):
            x, y = rect.left() + rect.width() * i / 4, rect.bottom() - rect.height() * i / 4
            p.setPen(QPen(GRID, 1)); p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        p.setPen(QPen(QColor("#48566d"), 1, Qt.DashLine)); p.drawLine(rect.bottomLeft(), rect.topRight())
        path = QPainterPath(rect.bottomLeft())
        for i in range(101):
            y = curve_value(i / 100, self.deadzone, self.gamma)
            path.lineTo(rect.left() + rect.width() * i / 100, rect.bottom() - rect.height() * y)
        p.setPen(QPen(self.color, 2.5)); p.drawPath(path)
        if self.active:
            x = rect.left() + rect.width() * self.cursor
            y = rect.bottom() - rect.height() * curve_value(self.cursor, self.deadzone, self.gamma)
            p.setPen(QPen(self.color, 1, Qt.DotLine)); p.drawLine(QPointF(x, rect.bottom()), QPointF(x, y))
            p.setBrush(self.color); p.setPen(QPen(QColor("#eafffa"), 2)); p.drawEllipse(QPointF(x, y), 5, 5)
        p.setPen(MUTED); p.setFont(QFont("Microsoft YaHei UI", 8))
        if self.hysteresis_on is not None:
            p.drawText(QRectF(rect.left(),rect.top()+3,rect.width()-4,18),Qt.AlignRight,
                       f"触发 {self.hysteresis_on/100:g}% / 释放 {self.deadzone/100:g}% · 启用后曲线")
        p.drawText(QRectF(0, 4, 29, 18), Qt.AlignRight, "100")
        p.drawText(QRectF(7, rect.bottom() - 8, 20, 18), Qt.AlignRight, "0")
        p.drawText(QRectF(rect.left(), rect.bottom() + 8, rect.width(), 19), Qt.AlignCenter, "输入行程 %   →   输出 %")


class StickView(QWidget):
    def __init__(self, color="#9f91ff", parent=None):
        super().__init__(parent)
        self.x, self.y, self.deadzone, self.active, self.color = 0., 0., 0., False, QColor(color)
        self.setMinimumSize(100, 100)

    def set_value(self, x, y, active=True):
        self.x, self.y = max(-1, min(1, x / 32767)), max(-1, min(1, y / 32767))
        self.active = active; self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = min(self.width(), self.height()) * .40; c = QPointF(self.width()/2, self.height()/2)
        p.setPen(QPen(GRID, 1)); p.setBrush(QColor("#101827")); p.drawEllipse(c, r, r)
        p.drawLine(QPointF(c.x()-r,c.y()), QPointF(c.x()+r,c.y()))
        p.drawLine(QPointF(c.x(),c.y()-r), QPointF(c.x(),c.y()+r))
        p.setPen(QPen(QColor("#536079"),1,Qt.DashLine)); p.drawEllipse(c,r*self.deadzone,r*self.deadzone)
        pt = QPointF(c.x()+self.x*r,c.y()-self.y*r)
        p.setPen(QPen(self.color if self.active else MUTED,2)); p.drawLine(c,pt)
        p.setBrush(self.color if self.active else MUTED); p.drawEllipse(pt,5,5)


class ControllerView(QWidget):
    """Scalable, original schematic; highlights the 14 XInput button bits."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons, self.active = 0, False
        self.setMinimumSize(320, 180)
        self.setToolTip("输入按钮示意；颜色亮起表示所选数据层的按钮已按下。")

    def set_value(self, buttons, active=True):
        self.buttons, self.active = int(buttons), active; self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width()/2,self.height()/2); scale=min(self.width()/400,self.height()/220); p.scale(scale,scale)
        path=QPainterPath(); path.moveTo(-134,-66); path.cubicTo(-173,-70,-187,4,-183,67)
        path.cubicTo(-178,111,-141,85,-109,50); path.lineTo(109,50)
        path.cubicTo(141,85,178,111,183,67); path.cubicTo(187,4,173,-70,134,-66)
        path.cubicTo(60,-83,-60,-83,-134,-66)
        p.setBrush(QColor("#1b273a")); p.setPen(QPen(QColor("#38465f"),2)); p.drawPath(path)
        positions=[(-85,0),(-85,38),(-104,19),(-66,19),(27,-25),(-27,-25),(-116,-36),(54,32),(-113,-78),(113,-78),(111,19),(137,-7),(85,-7),(111,-33)]
        colors={10:"#43ddbd",11:"#f68b9c",12:"#76b6ff",13:"#f5cd75"}
        for i,(x,y) in enumerate(positions):
            lit=self.active and bool(self.buttons & (1<<BITS[i])); color=QColor(colors.get(i,"#9f91ff"))
            p.setBrush(color if lit else QColor("#101827")); p.setPen(QPen(color if lit else QColor("#43516a"),1.5))
            rect=QRectF(x-15,y-11,30,22)
            p.drawRoundedRect(rect,7,7)
            p.setPen(QColor("#0d1320") if lit else QColor("#a0adc3")); p.setFont(QFont("Segoe UI",7,QFont.Bold))
            p.drawText(rect,Qt.AlignCenter,BUTTONS[i])
        p.setPen(QColor("#43ddbd") if self.active else MUTED); p.setFont(QFont("Segoe UI",8,QFont.DemiBold))
        p.drawText(QRectF(-43,4,86,25),Qt.AlignCenter,"RP2350")
