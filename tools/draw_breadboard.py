"""Deterministic breadboard illustration; a wiring assumption, not measured hardware."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/images/breadboard-dual-pedals.png'
OUT.parent.mkdir(parents=True, exist_ok=True)
im = Image.new('RGB', (2200, 1510), '#f4f6fa')
d = ImageDraw.Draw(im)
REG = 'C:/Windows/Fonts/msyh.ttc'
BOLD = 'C:/Windows/Fonts/msyhbd.ttc'
RED, BLACK, SIGNAL, AXIS0, AXIS1 = '#dc3545', '#303b4a', '#d99b00', '#008876', '#326ac5'
def txt(x,y,s,size=25,fill='#243246',bold=False,anchor=None):
    d.text((x,y),s,font=ImageFont.truetype(BOLD if bold else REG,size),fill=fill,anchor=anchor)
def line(points,color,width=7):
    # A pale casing distinguishes insulated jumper crossings from junctions.
    d.line(points,fill='#f4f6fa',width=width+6,joint='curve')
    d.line(points,fill=color,width=width,joint='curve')
def dot(x,y,color,r=7):
    d.ellipse((x-r,y-r,x+r,y+r),fill=color,outline='white',width=2)
def wire(points,color):
    line(points,color)
    dot(*points[0],color);dot(*points[-1],color)
def y(row): return 340 + (row-1)*30
cols = dict(zip('abcdefghij',[760,805,850,895,940,1140,1185,1230,1275,1320]))
def hole(name): return cols[name[0]], y(int(name[1:]))
def resistor(top,bottom,label,side=1):
    x,ya=hole(top); xb,yb=hole(bottom); assert x==xb
    d.line([(x,ya),(x,yb)],fill='#89939e',width=5)
    center=(ya+yb)//2
    d.rounded_rectangle((x-15,center-28,x+15,center+28),radius=7,fill='#e5c990',outline='#705c35',width=2)
    for dy,c in [(-15,'#895524'),(-5,'#202020'),(5,'#d88c21'),(18,'#b5a24c')]:
        d.line([(x-13,center+dy),(x+13,center+dy)],fill=c,width=5)
    txt(x+23 if side>0 else x-66,center-17,label,25,bold=True)
    dot(x,ya,'#89939e',5);dot(x,yb,'#89939e',5)
def capacitor(top,bottom,label,side=1):
    x,ya=hole(top);_,yb=hole(bottom);cy=(ya+yb)//2
    d.line([(x,ya),(x,yb)],fill='#89939e',width=4)
    d.ellipse((x-18,cy-19,x+18,cy+19),fill='#d47c26',outline='#925214',width=2)
    txt(x,cy,'104',14,fill='white',bold=True,anchor='mm')
    txt(x+23 if side>0 else x-62,cy-15,label,24,bold=True)
    dot(x,ya,'#89939e',5);dot(x,yb,'#89939e',5)

txt(40,25,'双踏板 · 面包板接线图',44,bold=True)
txt(42,91,'适用假设：三线模拟传感器；红 = +5V，黑 = GND，白/黄 = 0～5V OUT。厂家线序尚未核实。',25,fill='#9a5816')
txt(42,129,'元件：10kΩ 电阻 × 4，100nF 陶瓷电容（104，无正负）× 2。先断电接线。',25)

# Breadboard: two isolated five-hole groups per row, and four independent rails.
d.rounded_rectangle((520,280,1560,970),radius=25,fill='#e8ebee',outline='#b8c0c9',width=3)
d.rounded_rectangle((1010,320,1070,935),radius=13,fill='#c9ced5')
for rail,color,mark in [(580,RED,'+'),(625,BLACK,'−'),(1450,BLACK,'−'),(1495,RED,'+')]:
    d.line([(rail,325),(rail,930)],fill=color,width=3)
    txt(rail,300,mark,26,fill=color,bold=True,anchor='mm')
    for row in range(1,21):
        d.ellipse((rail-5,y(row)-5,rail+5,y(row)+5),fill='#7d8792')
for key,x in cols.items(): txt(x,300,key,24,bold=True,anchor='mm')
for row in range(1,21):
    for first,last in [('a','e'),('f','j')]:
        color={6:'#e6c665',10:'#7cc5b5',12:'#a2adb9',14:'#a2adb9'}.get(row,'#d7dce2')
        d.line([(cols[first],y(row)),(cols[last],y(row))],fill=color,width=12)
    txt(700,y(row),str(row),21,anchor='mm')
    txt(1380,y(row),str(row),21,anchor='mm')
    for x in cols.values():
        d.ellipse((x-6,y(row)-6,x+6,y(row)+6),fill='#65717e',outline='#fbfcfd',width=2)

# External supply is explicit: no invented 5V header on the RP2350 board.
d.rounded_rectangle((35,175,405,310),radius=15,fill='white',outline='#b7c2d2',width=2)
txt(55,185,'独立 5V 电源',29,bold=True)
txt(55,230,'正极 +',24,fill=RED);txt(55,268,'负极 −',24,fill=BLACK)
wire([(405,240),(470,240),(470,200),(580,200),(580,y(1))],RED)
wire([(405,280),(625,280),(625,y(1))],BLACK)
wire([(580,y(3)),(580,220),(1495,220),(1495,y(3))],RED)
wire([(625,y(3)),(625,250),(1450,250),(1450,y(3))],BLACK)
txt(930,177,'两侧红轨相连；两侧地轨相连',23,anchor='mm')

def sensor(x,title,right=False):
    d.rounded_rectangle((x,380,x+340,655),radius=18,fill='white',outline='#b7c2d2',width=2)
    txt(x+20,393,title,31,bold=True)
    for yy,label,color in [(450,'红：+5V',RED),(490,'黑：GND',BLACK),(530,'白/黄：OUT',SIGNAL)]:
        txt(x+20,yy-13,label,24,fill=color)
    txt(x+20,590,'配色属于本图假设',22,fill='#9a5816')
    return x if right else x+340
left = sensor(35,'油门传感器')
right = sensor(1825,'刹车传感器',True)
wire([(left,450),(440,450),(440,320),(580,320),(580,y(2))],RED)
wire([(left,490),(470,490),(470,y(5)),(625,y(5))],BLACK)
wire([(left,530),(485,530),(485,y(6)),hole('a6')],SIGNAL)
wire([(right,450),(1700,450),(1700,320),(1495,320),(1495,y(2))],RED)
wire([(right,490),(1660,490),(1660,y(5)),(1450,y(5))],BLACK)
wire([(right,530),(1630,530),(1630,y(6)),hole('j6')],SIGNAL)

# Output jumpers use row gaps / center trench so they cannot be mistaken for holes.
wire([hole('c10'),(850,598),(1040,598),(1040,1100)],AXIS0)
wire([hole('h10'),(1230,598),(1405,598),(1405,1100)],AXIS1)
wire([hole('a12'),(625,y(12))],BLACK)
wire([hole('a14'),(625,y(14))],BLACK)
wire([hole('j12'),(1450,y(12))],BLACK)
wire([hole('j14'),(1450,y(14))],BLACK)
resistor('b6','b10','R1')
resistor('d10','d14','R2',-1)
capacitor('e10','e12','C1')
resistor('i6','i10','R3')
resistor('g10','g14','R4')
capacitor('f10','f12','C2',-1)
for xx,label,col in [(850,'同排 a–e 相通',AXIS0),(1230,'同排 f–j 相通',AXIS1)]:
    d.rounded_rectangle((xx-130,820,xx+130,868),radius=8,fill='#f8fafc')
    txt(xx,844,label,25,fill=col,bold=True,anchor='mm')

# MCU is deliberately a logical terminal block, not a fabricated board pinout.
d.rounded_rectangle((950,1100,1590,1320),radius=20,fill='#184b4c',outline='#103436',width=3)
txt(1270,1190,'微雪 RP2350-USB-A',32,fill='white',bold=True,anchor='mm')
txt(1270,1234,'只示意端子名称，不表示实物针脚位置',22,fill='#c5e1db',anchor='mm')
dot(1040,1100,AXIS0,10);dot(1405,1100,AXIS1,10)
txt(1040,1133,'GP26',28,fill='white',bold=True,anchor='mm')
txt(1405,1133,'GP27',28,fill='white',bold=True,anchor='mm')
wire([(625,y(13)),(625,1020),(880,1020),(880,1275),(950,1275)],BLACK)
txt(975,1260,'GND',26,fill='white',bold=True)
txt(1615,1165,'Type-C 接电脑',25,bold=True)
txt(1615,1205,'不使用 USB-A 插座',23)
txt(1615,1250,'本图的 5V 来自独立电源',22)

d.rounded_rectangle((35,1010,790,1320),radius=18,fill='white',outline='#b7c2d2',width=2)
txt(60,1025,'照孔位插：元件两脚必须在不同排',28,bold=True)
for i,s in enumerate(['油门：OUT→a6；R1：b6、b10；R2：d10、d14',
                       'C1：e10、e12；c10→GP26',
                       '刹车：OUT→j6；R3：i6、i10；R4：g10、g14',
                       'C2：f10、f12；h10→GP27',
                       'a12、a14、j12、j14 各用跳线接地轨',
                       'R1～R4 均为 10kΩ；C1、C2 均为 104']):
    txt(60,1077+35*i,s,22)

for row in range(1,21):
    for xx in [700,1380]:
        d.rounded_rectangle((xx-17,y(row)-13,xx+17,y(row)+13),radius=3,fill='#e8ebee')
        txt(xx,y(row),str(row),21,anchor='mm')
txt(40,1360,'连接检查：中间沟两侧不通；跳线只在两端插孔，中途跨过的孔不算连接。',26,bold=True)
txt(40,1400,'① 电源负极、两根黑线、开发板GND必须共地。  ② 5V红轨绝不能与地轨短接。',25)
txt(40,1442,'③ 不向开发板3V3接入5V。  ④ 此图仅适用于上述配色和0～5V模拟输出假设；未知线序仍可能接错。',24,fill='#9a5816')
im.save(OUT)
print(OUT)
