"""Generate the carrier schematic from its explicit electrical contract.

Run --init-model once to create the initial model. Normal runs preserve the
model, including placement changes made during PCB layout.
"""
from pathlib import Path
import argparse
import csv
import json
import math
import re
import copy
import uuid

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'hardware/carrier'
NS = uuid.UUID('e2350a00-9555-4685-8020-000000000001')
LIB = ROOT / 'deps/kicad/share/kicad/symbols'


def parse(text):
    """Parse KiCad lists preserving raw atom quoting for lossless library reuse."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack, result = [], None
    for token in tokens:
        if token == '(':
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
        elif token == ')':
            result = stack.pop()
        else:
            stack[-1].append(token)
    return result


def sexpr(value):
    return '(' + ' '.join(sexpr(v) if isinstance(v, list) else str(v) for v in value) + ')'


def q(value):
    return json.dumps(str(value), ensure_ascii=False)


def children(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def child(node, key):
    return children(node, key)[0]


def unq(value):
    return json.loads(value) if value.startswith('"') else value


def library_symbol(lib_id):
    lib, name = lib_id.split(':')
    if lib == 'Carrier':
        return module_symbol()
    ast = parse((LIB / (lib + '.kicad_sym')).read_text(encoding='utf-8'))
    symbols = {unq(x[1]): x for x in children(ast,'symbol')}
    def resolve(name):
        sym = copy.deepcopy(symbols[name])
        if children(sym,'extends'):
            base = resolve(unq(child(sym,'extends')[1]))
            propkeys = {x[1] for x in children(sym,'property')}
            inherited = [x for x in base[2:] if not (isinstance(x,list) and x[0]=='property' and x[1] in propkeys)]
            sym = sym[:2] + [x for x in sym[2:] if not (isinstance(x,list) and x[0]=='extends')] + inherited
        return sym
    sym = resolve(name)
    sym[1] = q(lib_id)
    return sym


def module_symbol():
    name = 'Waveshare_RP2350_USB_A'
    sym = ['symbol',q('Carrier:'+name),['pin_names',['offset','0.7']],
           ['in_bom','yes'],['on_board','yes'],
           ['property',q('Reference'),q('U'),['at','0','27.94','0'],['effects',['font',['size','1.27','1.27']]]],
           ['property',q('Value'),q('RP2350-USB-A'),['at','0','25.4','0'],['effects',['font',['size','1.27','1.27']]]],
           ['symbol',q(name+'_0_1'),['rectangle',['start','-17.78','22.86'],['end','17.78','-22.86'],['stroke',['width','0.254'],['type','default']],['fill',['type','background']]]]]
    body=['symbol',q(name+'_1_1')]
    # Match official top-view row ordering; actual footprint is rotated for USB clearance.
    left=[18,17,16,15,14,13,12,11,10]
    right=list(range(1,10))
    names={**{i+1:f'GP{i}' for i in range(11)},12:'GP26 / ADC0',13:'GP27 / ADC1',14:'GP28 / ADC2',15:'GP29 / ADC3',16:'3V3 OUT',17:'GND',18:'VSYS USB5V'}
    for side,numbers in [(-1,left),(1,right)]:
        for row,num in enumerate(numbers):
            ptype='power_out' if num in [16,18] else 'power_in' if num==17 else 'bidirectional'
            body.append(['pin',ptype,'line',['at',str(side*22.86),str(20.32-row*5.08),'0' if side<0 else '180'],['length','5.08'],
                         ['name',q(names[num]),['effects',['font',['size','1.0','1.0']]]],
                         ['number',q(num),['effects',['font',['size','1.0','1.0']]]]])
    sym.append(body)
    return sym


def uid(name):
    return str(uuid.uuid5(NS, name))


def initial_model():
    c = {}
    def add(ref, value, symbol, footprint, pins, **extra):
        c[ref] = dict(value=value, symbol=symbol, footprint=footprint,
                      pins={str(k): v for k, v in pins.items()}, uuid=uid(ref), **extra)
    def resistor(n, value, a, b, purpose):
        add(f'R{n}', value, 'Device:R', 'Resistor_SMD:R_0805_2012Metric',
            {1: a, 2: b}, purpose=purpose)
    def cap(n, value, a, purpose):
        add(f'C{n}', value, 'Device:C', 'Capacitor_SMD:C_0805_2012Metric',
            {1: a, 2: 'GND'}, purpose=purpose)
    def header(ref, value, nets, rows=1):
        count = len(nets)
        name = f'Conn_0{rows}x{count//rows:02}' + ('_Odd_Even' if rows == 2 else '')
        fp = f'PinHeader_{rows}x{count//rows:02}_P2.54mm_Vertical'
        add(ref, value, 'Connector_Generic:' + name,
            'Connector_PinHeader_2.54mm:' + fp, dict(enumerate(nets, 1)))
    module = ['I2C_SDA', 'I2C_SCL', 'ENC_A', 'ENC_B', 'SPI_MISO', 'SPI_CS',
              'SPI_SCK', 'SPI_MOSI', 'FFB_EN_MCU', 'FFB_IRQ_N', 'MODE_N',
              'ADC_THROTTLE', 'ADC_BRAKE', 'ADC_CLUTCH', 'ADC_AUX',
              '+3V3', 'GND', '+5V_USB']
    add('U1', 'Waveshare RP2350-USB-A', 'Carrier:Waveshare_RP2350_USB_A',
        'Carrier:Waveshare_RP2350_USB_A', dict(enumerate(module, 1)),
        mpn='Waveshare RP2350-USB-A', purpose='Plug-in USB controller module',
        assembly='Two 1x09 2.54mm female sockets, 15.24mm row spacing; then plug module into sockets')
    gpio = {1: None, 2: 'GND', 3: 'GND', 12: 'GND', 21: 'GND',
            22: 'I2C_SCL', 23: 'I2C_SDA', 24: '+3V3'}
    gpio.update({p: f'BTN{i:02}' for i, p in enumerate(list(range(4,12))+list(range(13,21)), 1)})
    add('U2', 'PCA9555D', 'Interface_Expansion:PCA9555D',
        'Package_SO:SOIC-24W_7.5x15.4mm_P1.27mm', gpio,
        mpn='PCA9555D,118', manufacturer='NXP', purpose='16 active-low buttons; poll over I2C',
        datasheet='https://www.nxp.com/docs/en/data-sheet/PCA9555.pdf',
        unused_pins={'1': 'Interrupt unused: firmware polls all 16 inputs'})
    pwm = {i: None for i in range(1,29)}
    pwm.update({i: 'GND' for i in [1,2,3,4,5,14,24,25]})
    pwm.update({6:'PWM0_RAW', 7:'PWM1_RAW', 8:'PWM2', 9:'PWM3', 23:'PWM_OE_N',
                26:'I2C_SCL', 27:'I2C_SDA', 28:'+3V3'})
    add('U3', 'PCA9685PW', 'Driver_LED:PCA9685PW',
        'Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm', pwm,
        mpn='PCA9685PW,118', manufacturer='NXP', purpose='Two haptic PWM signals; two spare',
        datasheet='https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf',
        unused_pins={str(i): 'Unused PWM output' for i in list(range(10,14))+list(range(15,23))})
    for i, name in enumerate(['THROTTLE','BRAKE','CLUTCH','AUX'],1):
        raw, adc = 'ANALOG_'+name, 'ADC_'+name
        add(f'J{i}', name+' 5V/GND/OUT', 'Connector_Generic:Conn_01x03',
            'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal',
            {1:'+5V_SENSOR',2:'GND',3:raw}, mpn='Phoenix Contact 1715734',
            purpose='0..5V analog sensor only')
        resistor(2*i-1,'10k 1%',raw,adc,'Divider upper arm; no bypass')
        resistor(2*i,'10k 1%',adc,'GND','Divider lower arm')
        cap(i,'100nF 16V X7R',adc,'ADC low-pass 318 Hz nominal')
        add(f'D{i}', 'PESD5V0S1BA', 'Device:D_TVS', 'Diode_SMD:D_SOD-323',
            {1:raw,2:'GND'}, mpn='PESD5V0S1BA,115', manufacturer='Nexperia',
            purpose='Connector ESD shunt; not DC overvoltage protection',
            datasheet='https://assets.nexperia.com/documents/data-sheet/PESD5V0S1BA.pdf')
    header('J5','BUTTONS 01-08/GND',[f'BTN{i:02}' for i in range(1,9)]+['GND'])
    header('J6','BUTTONS 09-16/GND',[f'BTN{i:02}' for i in range(9,17)]+['GND'])
    for i in range(1,17):
        resistor(i+8,'10k 1%','+3V3',f'BTN{i:02}','External pull-up; switch to GND')
    header('J7','ENCODER 3V3/GND/A/B',['+3V3','GND','ENC_A','ENC_B'])
    header('J8','I2C 3V3/GND/SDA/SCL',['+3V3','GND','I2C_SDA','I2C_SCL'])
    header('J9','HAPTIC1 3V3/GND/PWM',['+3V3','GND','HAPTIC1'])
    header('J10','HAPTIC2 3V3/GND/PWM',['+3V3','GND','HAPTIC2'])
    header('J11','SPI DAUGHTERCARD 3V3 ONLY',
           ['+3V3','GND','SPI_SCK','GND','SPI_MOSI','SPI_MISO','SPI_CS','FFB_EN','FFB_IRQ_N','GND'],2)
    header('J12','MODE switch/GND',['MODE_N','GND'])
    header('J13','PWM SPARE 3V3/GND/2/3',['+3V3','GND','PWM2','PWM3'])
    header('JP1','PWM ENABLE: OPEN=OFF',['PWM_OE_N','GND'])
    c['JP1']['assembly'] = 'Fit header; leave shunt REMOVED by default'
    resistor(25,'4.7k 1%','+3V3','I2C_SDA','I2C pull-up to 3.3V only')
    resistor(26,'4.7k 1%','+3V3','I2C_SCL','I2C pull-up to 3.3V only')
    resistor(27,'10k 1%','+3V3','ENC_A','Encoder pull-up; mechanical contact or 3.3V/open drain')
    resistor(28,'10k 1%','+3V3','ENC_B','Encoder pull-up')
    resistor(29,'10k 1%','+3V3','FFB_IRQ_N','Open-drain 3.3V fault/IRQ pull-up')
    resistor(30,'330R 1%','FFB_EN_MCU','FFB_EN','Non-safety EN series damping/current limiting')
    resistor(31,'10k 1%','FFB_EN','GND','EN default low; not STO')
    resistor(32,'330R 1%','PWM0_RAW','HAPTIC1','PWM control output series damping')
    resistor(33,'10k 1%','HAPTIC1','GND','Haptic1 default low when unpowered/high-Z')
    resistor(34,'330R 1%','PWM1_RAW','HAPTIC2','PWM control output series damping')
    resistor(35,'10k 1%','HAPTIC2','GND','Haptic2 default low when unpowered/high-Z')
    resistor(36,'10k 1%','+3V3','PWM_OE_N','OE high disables outputs with default MODE2')
    resistor(37,'10k 1%','+3V3','MODE_N','Future GP10 mode input; current firmware uses unexposed GP14')
    cap(5,'100nF 16V X7R','+3V3','U2 local decoupling')
    cap(6,'100nF 16V X7R','+3V3','U3 local decoupling')
    cap(7,'4.7uF 10V X7R','+3V3','Logic rail bulk decoupling')
    cap(8,'4.7uF 10V X7R','+5V_SENSOR','Sensor branch bulk decoupling')
    cap(9,'100nF 16V X7R','+5V_SENSOR','Sensor branch HF decoupling')
    add('F1','PTC 0.25A hold', 'Device:Polyfuse', 'Fuse:Fuse_1206_3216Metric',
        {1:'+5V_USB',2:'+5V_SENSOR'}, mpn='MF-NSMF025X-2', manufacturer='Bourns',
        datasheet='https://www.bourns.com/docs/product-datasheets/mf-nsmf.pdf',
        purpose='Sensor branch short-circuit mitigation, not accurate current limiting')
    for i in range(1,5):
        add(f'H{i}', 'M3 NPTH', 'Mechanical:MountingHole',
            'MountingHole:MountingHole_3.2mm_M3', {}, purpose='Mechanical mounting hole')
    return dict(schema_version=1, title='RP2350-USB-A expandable carrier V0.1',
                components=c, nets=sorted({n for p in c.values() for n in p['pins'].values() if n}),
                i2c_addresses={'U2':'0x20','U3':'0x40','U3_allcall':'0x70'},
                schematic_uuid=uid('schematic'), board=dict(width_mm=100,height_mm=80,layers=2))


def schematic_positions():
    pos = {'U1':(100,95), 'U2':(355,90), 'U3':(620,90),
           'F1':(215,65), 'C8':(205,110), 'C9':(250,110), 'C7':(210,160),
           'C5':(305,90), 'C6':(570,90), 'J5':(455,65), 'J6':(510,65),
           'J7':(75,285), 'J8':(175,285), 'J12':(255,285),
           'J9':(770,45), 'J10':(770,95), 'J13':(770,145), 'JP1':(770,200),
           'R25':(140,340), 'R26':(190,340), 'R27':(40,340), 'R28':(90,340),
           'R37':(240,340), 'J11':(410,285), 'R29':(325,345),
           'R30':(410,345), 'R31':(480,345), 'R32':(700,45), 'R33':(700,70),
           'R34':(700,105), 'R35':(700,130), 'R36':(680,200)}
    for i in range(16):
        pos[f'R{i+9}'] = (320 + (i%4)*55, 150 + (i//4)*25)
    for i in range(1,5):
        x=40+(i-1)*205
        pos.update({f'J{i}':(x+25,450),f'D{i}':(x+20,505),
                    f'R{2*i-1}':(x+90,450),f'R{2*i}':(x+90,505),f'C{i}':(x+140,505)})
        pos[f'H{i}']=(585+(i-1)*55,350)
    # Symbols and wires must be on the 1.27 mm grid, including all endpoints.
    return {ref:tuple(round(v*0.7/1.27)*1.27 for v in xy) for ref,xy in pos.items()}


def draw_schematic(model):
    ids=sorted({p['symbol'] for p in model['components'].values()} | {'power:PWR_FLAG'})
    symbols={i:library_symbol(i) for i in ids}
    root_uuid=model['schematic_uuid']
    sheet=['kicad_sch',['version','20250114'],['generator',q('eeschema')],
           ['uuid',q(root_uuid)],['paper',q('A2')],
           ['title_block',['title',q('RP2350-USB-A EXPANDABLE CARRIER')],['date',q('2026-11-06')],
            ['rev',q('V0.1 ENGINEERING SAMPLE')],['company',q('3.3V logic | 5V analog sensors | NO MOTOR POWER')]],
           ['lib_symbols',*symbols.values()]]
    positions=schematic_positions()
    def effects(size=1.0,justify=None,hide=False):
        result=['effects',['font',['size',str(size),str(size)]]]
        if justify:
            result.append(['justify',justify])
        if hide:
            result.append(['hide','yes'])
        return result
    def wire(x1,y1,x2,y2,key):
        sheet.append(['wire',['pts',['xy',str(round(x1,4)),str(round(y1,4))],['xy',str(round(x2,4)),str(round(y2,4))]],
                      ['stroke',['width','0'],['type','default']],['uuid',q(uid(key))]])
    def label(name,x,y,angle,key):
        sheet.append(['label',q(name),['at',str(round(x,4)),str(round(y,4)),str(angle)],
                      effects(1.0,'left' if angle in (0,90) else 'right'),['uuid',q(uid(key))]])
    for ref,part in model['components'].items():
        x,y=positions[ref]
        sym=symbols[part['symbol']]
        pins=[pin for body in children(sym,'symbol') for pin in children(body,'pin')]
        if {unq(child(p,'number')[1]) for p in pins} != set(part['pins']):
            raise ValueError(f'{ref}: library pins do not match electrical model')
        node=['symbol',['lib_id',q(part['symbol'])],['at',str(x),str(y),'0'],['unit','1'],
              ['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',q(part['uuid'])]]
        if ref.startswith('U'):
            dx,dy=0,-(32 if ref != 'U1' else 27)
        elif ref.startswith(('J','H')):
            dx,dy=0,-(16 if ref in ['J5','J6'] else 11)
        elif ref.startswith('D'):
            dx,dy=0,-6.35
        else:
            dx,dy=4,-1.27
        node.append(['property',q('Reference'),q(ref),['at',str(x+dx),str(y+dy),'0'],effects(1.27)])
        node.append(['property',q('Value'),q(part['value']),['at',str(x+dx),str(y+dy+2.54),'0'],effects(1.0)])
        node.append(['property',q('Footprint'),q(part['footprint']),['at',str(x),str(y),'0'],effects(hide=True)])
        node.append(['property',q('Datasheet'),q(part.get('datasheet','')),['at',str(x),str(y),'0'],effects(hide=True)])
        for pin in pins:
            num=unq(child(pin,'number')[1])
            node.append(['pin',q(num),['uuid',q(uid(ref+':pin:'+num))]])
            px,py,pa=map(float,child(pin,'at')[1:4])
            px,py=x+px,y-py
            net=part['pins'][num]
            if net is None:
                sheet.append(['no_connect',['at',str(round(px,4)),str(round(py,4))],['uuid',q(uid(ref+':nc:'+num))]])
                continue
            # Draw the ADC filter as a connected divider/RC circuit rather than detached labels.
            analogue_joined = any((ref,num) in [(f'R{2*i-1}','2'),(f'R{2*i}','1'),(f'C{i}','1')] for i in range(1,5))
            if analogue_joined:
                continue
            # Pin angle points into body. Extend wire away from body.
            stub=2.54 if ref.startswith(('R','C','D','F')) else 5.08
            dx=-stub*round(math.cos(math.radians(pa)))
            dy=stub*round(math.sin(math.radians(pa)))
            ex,ey=px+dx,py+dy
            wire(px,py,ex,ey,ref+':wire:'+num)
            # Horizontal labels extend away from symbol. Vertical terminals use horizontal labels.
            angle=180 if dx<0 else 0
            label(net,ex,ey,angle,ref+':label:'+num)
        node.append(['instances',['project',q('carrier'),['path',q('/'+root_uuid),['reference',q(ref)],['unit','1']]]])
        sheet.append(node)
    for i,name in enumerate(['THROTTLE','BRAKE','CLUTCH','AUX'],1):
        ux,uy=positions[f'R{2*i-1}']
        lx,ly=positions[f'R{2*i}']
        cx,cy=positions[f'C{i}']
        wire(ux,uy+3.81,lx,ly-3.81,f'ADC{i}:divider')
        wire(lx,ly-3.81,cx,cy-3.81,f'ADC{i}:capacitor')
        sheet.append(['junction',['at',str(lx),str(round(ly-3.81,4))],['diameter','0'],['color','0','0','0','0'],['uuid',q(uid(f'ADC{i}:junction'))]])
        label('ADC_'+name,cx,cy-3.81,0,f'ADC{i}:label')
    # Explicit ground power source declaration: power originates at the plugged-in USB module.
    x,y=177.8,119.38
    flag=['symbol',['lib_id',q('power:PWR_FLAG')],['at',str(x),str(y),'0'],['unit','1'],
          ['in_bom','no'],['on_board','yes'],['dnp','no'],['uuid',q(uid('ground_power_flag'))],
          ['property',q('Reference'),q('#FLG01'),['at',str(x),str(y),'0'],effects(hide=True)],
          ['property',q('Value'),q('PWR_FLAG'),['at',str(x),str(y-4),'0'],effects(1)],
          ['pin',q('1'),['uuid',q(uid('ground_power_flag:pin'))]],
          ['instances',['project',q('carrier'),['path',q('/'+root_uuid),['reference',q('#FLG01')],['unit','1']]]]]
    sheet.append(flag)
    wire(x,y,x,y+5.08,'ground_flag_wire')
    label('GND',x,y+5.08,0,'ground_flag_label')
    def note(text,x,y,size=1.5):
        x,y=x*0.7,y*0.7
        sheet.append(['text',q(text),['at',str(x),str(y),'0'],effects(size,'left'),['uuid',q(uid('note:'+text))]])
    def box(x1,y1,x2,y2):
        x1,y1,x2,y2=[v*0.7 for v in (x1,y1,x2,y2)]
        sheet.append(['polyline',['pts',['xy',str(x1),str(y1)],['xy',str(x2),str(y1)],['xy',str(x2),str(y2)],['xy',str(x1),str(y2)],['xy',str(x1),str(y1)]],
                      ['stroke',['width','0.254'],['type','default']],['fill',['type','none']],['uuid',q(uid(f'box{x1}{y1}'))]])
    for bounds,title in [((15,15,275,245),'01  MODULE / USB-DERIVED POWER'),
                         ((285,15,540,245),'02  SIXTEEN ACTIVE-LOW BUTTONS / I2C 0x20'),
                         ((550,15,825,245),'03  HAPTIC CONTROL ONLY / I2C 0x40'),
                         ((15,255,275,385),'04  ENCODER / SCREEN / FUTURE MODE'),
                         ((285,255,540,385),'05  SPI INTERFACE DAUGHTERCARD'),
                         ((550,255,825,385),'06  LIMITS / MECHANICAL')]:
        box(*bounds)
        note(title,bounds[0]+5,bounds[1]+7)
    note('U1 pin numbering follows manufacturer P1.\nUSB and regulator remain on module.\nF1 protects ONLY the shared sensor branch.\nNo independent supply may drive a port when OFF.',25,195)
    note('U2: inputs at reset. INT unused: poll.\nR9-R24 pull up; buttons close to GND.',300,133,1.1)
    note('JP1 OPEN = disabled (factory/default assembly).\nShort only after configuring all PWM channels OFF.\nKeep MODE2 OUTNE=00; no autonomous watchdog.\nPWM2/3 spare; unused PWM outputs explicitly NC.',565,222,1.15)
    note('3.3V logic only. I2C 100kHz initial target.\nGP10 is future MODE; current GP14 is not on P1.',25,370,1.2)
    note('EN default LOW; ordinary logic, NOT STO.\nIRQ is 3.3V open-drain only. No motor-power pins.\nExternal servo driver/protocol remains unselected.',300,370,1.2)
    note('ENGINEERING SAMPLE - NOT POWERED/VALIDATED\nNo servo motor driver or safety circuit on this PCB.\nADC input: 0..5V only; all sensors powered by board.\nESD TVS is NOT a guarantee against DC overvoltage.\nDo not hot-plug or inject signals while unpowered.\nCurrent firmware does not implement these expansions.\nSee circuit-notes.md for USB budget and limits.',565,280,1.35)
    for i,name in enumerate(['THROTTLE GP26','BRAKE GP27','CLUTCH GP28','AUX GP29'],1):
        x=15+(i-1)*205
        box(x,400,x+195,535)
        note(f'0{6+i}  ANALOG {name}',x+5,408)
        note('1=5V_SENSOR  2=GND  3=OUT\nFixed 1:2 divider; fc ~318Hz; no bypass.\nTVS at connector; capacitor near ADC.',x+5,520,1.15)
    (OUT/'carrier.kicad_sch').write_text(sexpr(sheet)+'\n',encoding='utf-8')
    # Store the custom symbol locally so the project remains editable without the generator.
    module=copy.deepcopy(symbols['Carrier:Waveshare_RP2350_USB_A'])
    module[1]=q('Waveshare_RP2350_USB_A')
    (OUT/'Carrier.kicad_sym').write_text(sexpr(['kicad_symbol_lib',['version','20250114'],['generator',q('kicad_symbol_editor')],module])+'\n',encoding='utf-8')
    entries=[['lib',['name',q('Carrier')],['type',q('KiCad')],['uri',q('${KIPRJMOD}/Carrier.kicad_sym')],['options',q('')],['descr',q('Verified Waveshare RP2350-USB-A module pinout')]]]
    for lib in sorted({i.split(':')[0] for i in ids if not i.startswith('Carrier:')}):
        entries.append(['lib',['name',q(lib)],['type',q('KiCad')],['uri',q('${KICAD10_SYMBOL_DIR}/'+lib+'.kicad_sym')],['options',q('')],['descr',q('Official KiCad 10 library')]])
    (OUT/'sym-lib-table').write_text(sexpr(['sym_lib_table',['version','7'],*entries])+'\n',encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init-model', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.init_model:
        (OUT/'design.json').write_text(json.dumps(initial_model(),indent=2)+'\n',encoding='utf-8')
    model = json.loads((OUT/'design.json').read_text(encoding='utf-8'))
    draw_schematic(model)
    with (OUT/'bom.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f)
        writer.writerow(['Reference','Value','Footprint','Manufacturer','MPN','Purpose','Assembly'])
        for ref,p in model['components'].items():
            writer.writerow([ref,p['value'],p['footprint'],p.get('manufacturer',''),p.get('mpn',''),p.get('purpose',''),p.get('assembly','Fit')])
    print(f"Electrical model: {len(model['components'])} parts, {len(model['nets'])} nets")


if __name__ == '__main__':
    main()
