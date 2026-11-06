"""Build the engineering-sample carrier with KiCad's native pcbnew API.

Run with deps/kicad/bin/python.exe -I after loading deps/kicad/env.ps1.
The XML exported by Eeschema is the authority for net names and NC nets.
Use --import-session FILE to import the retained offline-router result.
"""
from pathlib import Path
import sys
import json
import argparse
import xml.etree.ElementTree as ET
import math
import pcbnew as p

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from board_geometry import module_pads, mounting_holes

OUT = ROOT / 'hardware/carrier'
LIBS = ROOT / 'deps/kicad/share/kicad/footprints'
MODELS = ROOT / 'deps/kicad/share/kicad/3dmodels'
mm = p.FromMM
def pt(x, y): return p.VECTOR2I(mm(x), mm(y))

def line(parent, start, end, layer, width=.15):
    s = p.PCB_SHAPE(parent)
    s.SetShape(p.S_SEGMENT); s.SetStart(pt(*start)); s.SetEnd(pt(*end))
    s.SetLayer(layer); s.SetWidth(mm(width)); parent.Add(s)

def rect(parent, x1, y1, x2, y2, layer, width=.15):
    for a,b in [((x1,y1),(x2,y1)),((x2,y1),(x2,y2)),((x2,y2),(x1,y2)),((x1,y2),(x1,y1))]:
        line(parent,a,b,layer,width)

def text(board, value, x, y, size=1, layer=p.F_SilkS, rotation=0):
    t=p.PCB_TEXT(board); t.SetText(value); t.SetPosition(pt(x,y)); t.SetLayer(layer)
    t.SetTextSize(pt(size,size)); t.SetTextThickness(mm(.15 if size>=1 else .12))
    t.SetTextAngle(p.EDA_ANGLE(rotation,p.DEGREES_T)); board.Add(t); return t

def module_footprint():
    f=p.FOOTPRINT(None); f.SetReference('U1'); f.SetValue('Waveshare RP2350-USB-A')
    f.SetFPID(p.LIB_ID('Carrier','Waveshare_RP2350_USB_A')); f.SetAttributes(p.FP_THROUGH_HOLE)
    for n,(x,y) in module_pads().items():
        pad=p.PAD(f); pad.SetNumber(n); pad.SetAttribute(p.PAD_ATTRIB_PTH)
        pad.SetShape(p.PAD_SHAPE_RECT if n=='1' else p.PAD_SHAPE_CIRCLE)
        pad.SetSize(pt(1.8,1.8)); pad.SetDrillSize(pt(1,1)); pad.SetLayerSet(p.LSET.AllCuMask())
        ls=pad.GetLayerSet(); ls.AddLayer(p.F_Mask); ls.AddLayer(p.B_Mask); pad.SetLayerSet(ls)
        pad.SetPosition(pt(x,y)); f.Add(pad)
    rect(f,0,0,33,17.5,p.F_SilkS)
    rect(f,-1.5,-.5,33.5,18,p.F_CrtYd,.05)
    rect(f,0,0,33,17.5,p.F_Fab,.1)
    # Female socket bodies: 2.54 mm pitch, 15.24 mm separation.
    rect(f,1.61,-.14,24.47,2.4,p.F_Fab,.1)
    rect(f,1.61,15.1,24.47,17.64,p.F_Fab,.1)
    f.Reference().SetPosition(pt(17,8)); f.Value().SetVisible(False)
    model=p.FP_3DMODEL(); model.m_Filename='${KIPRJMOD}/3d/Waveshare_RP2350_USB_A_approx.wrl'
    f.Add3DModel(model)
    return f

def write_proxy():
    folder=OUT/'3d'; folder.mkdir(exist_ok=True)
    # KiCad VRML model units are 0.1 inch. Module board seats on 8.5 mm sockets.
    boxes=[((16.5,-8.75,9.3),(33,17.5,1.6),(.05,.15,.1)),
           ((12.94,-1.13,4.25),(22.86,2.54,8.5),(.08,.08,.08)),
           ((12.94,-16.37,4.25),(22.86,2.54,8.5),(.08,.08,.08)),
           ((.5,-8.75,11.6),(6.5,9,3.2),(.65,.65,.65)),
           ((29,-8.75,12.1),(9,13,5.5),(.65,.65,.65))]
    s='#VRML V2.0 utf8\n# APPROXIMATE module/socket/USB envelopes; NOT enclosure-fit authority.\n'
    for center,size,color in boxes:
        c=' '.join(str(v/2.54) for v in center); z=' '.join(str(v/2.54) for v in size)
        rgb=' '.join(str(v) for v in color)
        s+=f'Transform {{ translation {c} children [ Shape {{ appearance Appearance {{ material Material {{ diffuseColor {rgb} }} }} geometry Box {{ size {z} }} }} ] }}\n'
    (folder/'Waveshare_RP2350_USB_A_approx.wrl').write_text(s,encoding='utf-8')

def placement():
    d={'U1':(2,10,0),'U2':(48,44,0),'U3':(83,41,0),
       'J5':(35,37,0),'J6':(61,37,0),'J7':(25,38,0),'J8':(96,58,0),
       'J9':(96,33,0),'J10':(96,45,0),'J11':(85,10,0),'J12':(24,51,0),
       'J13':(78,54,0),'JP1':(73,59,0),'F1':(5.4,34,90),
       'C5':(52,33,0),'C6':(90,36.5,90),'C7':(57,32,0),
       'C8':(5.4,39,90),'C9':(5.4,43,90),
       'R25':(32,31,0),'R26':(36,31,0),'R27':(23,32,0),'R28':(28,32,0),
       'R29':(91,11,90),'R30':(91,16,90),'R31':(91,21,90),
       'R32':(91,41.5,90),'R33':(91,45.2,90),'R34':(91,50,90),'R35':(91,53.7,90),
       'R36':(86,57,90),'R37':(20,48,0)}
    for i,(x,y) in enumerate(mounting_holes(),1): d[f'H{i}']=(x,y,0)
    for i,x in enumerate([11,33,55,77],1):
        d[f'J{i}']=(x,70,0); d[f'D{i}']=(x+10.16,61.9,90)
        ax=[20.12,17.58,15.04,12.5][i-1]
        d[f'C{i}']=(ax,30.5,270); d[f'R{i*2}']=(ax,35,90); d[f'R{i*2-1}']=(ax,40,90)
    for i in range(8):
        d[f'R{i+9}']=(29,37+2.54*i,0); d[f'R{i+17}']=(67,37+2.54*i,0)
    return d

def position_references(board):
    """Keep all assembly refs visible, avoiding copper openings and silk labels."""
    obstacles=[]
    for fp in board.GetFootprints():
        fp.Reference().SetVisible(False)
        for pad in fp.Pads():
            bb=pad.GetBoundingBox(); bb.Inflate(mm(.2)); obstacles.append(bb)
        for item in fp.GraphicalItems():
            if item.GetLayer()==p.F_SilkS and (not isinstance(item,p.PCB_TEXT) or item.IsVisible()):
                bb=item.GetBoundingBox(); bb.Inflate(mm(.12)); obstacles.append(bb)
    for item in board.GetDrawings():
        if item.GetLayer()==p.F_SilkS:
            bb=item.GetBoundingBox(); bb.Inflate(mm(.12)); obstacles.append(bb)
    for fp in sorted(board.GetFootprints(),key=lambda f: (f.GetReference()[0]!='J',f.GetReference())):
        t=fp.Reference(); t.SetVisible(True); x,y=fp.GetPosition(); x=p.ToMM(x); y=p.ToMM(y)
        candidates=[]
        if fp.GetReference() in ['U1','U2','U3']:
            candidates.append({'U1':(33,29,0),'U2':(48,54,0),'U3':(83,48,0)}[fp.GetReference()])
        for radius in [1.8,2.4,3,3.6,4.2,4.8,5.4,6,7,8]:
            for dx,dy in [(0,-radius),(radius,0),(-radius,0),(0,radius),(radius,-radius),(-radius,-radius),(radius,radius),(-radius,radius)]:
                candidates.extend([(x+dx,y+dy,0),(x+dx,y+dy,90)])
        for cx,cy,angle in candidates:
            t.SetPosition(pt(cx,cy)); t.SetTextAngle(p.EDA_ANGLE(angle,p.DEGREES_T)); bb=t.GetBoundingBox()
            if bb.GetLeft()<mm(.5) or bb.GetTop()<mm(.5) or bb.GetRight()>mm(99.5) or bb.GetBottom()>mm(79.5): continue
            if not any(bb.Intersects(o) for o in obstacles):
                bb.Inflate(mm(.12)); obstacles.append(bb); break
        else: raise RuntimeError('No silkscreen reference position: '+fp.GetReference())

def build():
    model=json.loads((OUT/'design.json').read_text(encoding='utf-8'))
    xml=ET.parse(OUT/'reports/carrier-netlist.xml').getroot()
    board=p.BOARD(); board.SetCopperLayerCount(2); board.GetDesignSettings().SetBoardThickness(mm(1.6))
    title=board.GetTitleBlock(); title.SetTitle(model['title']); title.SetRevision('V0.1 engineering sample')
    title.SetDate('2026-11-06'); title.SetCompany('3.3V logic / 5V sensors / no motor power')
    nets={}; pin_nets={}
    for el in xml.findall('./nets/net'):
        name=el.attrib['name']; net=p.NETINFO_ITEM(board,name); board.Add(net); nets[name]=net
        for node in el.findall('node'): pin_nets[(node.attrib['ref'],node.attrib['pin'])]=name
    ns=board.GetDesignSettings().m_NetSettings
    nc=ns.GetDefaultNetclass(); nc.SetTrackWidth(mm(.25)); nc.SetClearance(mm(.2)); nc.SetViaDiameter(mm(.6)); nc.SetViaDrill(mm(.3))
    power=p.NETCLASS('Power'); power.SetTrackWidth(mm(.6)); power.SetClearance(mm(.2)); power.SetViaDiameter(mm(.8)); power.SetViaDrill(mm(.4))
    ns.SetNetclass('Power',power); ns.SetNetclassPatternAssignment('/+*','Power')
    for name,net in nets.items(): net.SetNetClass(power if name.startswith('/+') else nc)
    local=OUT/'Carrier.pretty'; local.mkdir(exist_ok=True)
    write_proxy(); f=module_footprint(); p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(local),f)
    (OUT/'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "Carrier")(type "KiCad")(uri "${KIPRJMOD}/Carrier.pretty")(options "")(descr "Project module footprint, official hole coordinates"))\n)\n',encoding='utf-8')
    places=placement(); fps={}
    for ref,c in model['components'].items():
        lib,name=c['footprint'].split(':',1)
        fp=p.FootprintLoad(str(local if lib=='Carrier' else LIBS/f'{lib}.pretty'),name)
        if not fp: raise RuntimeError(f'Footprint missing: {c["footprint"]}')
        board.Add(fp); fp.SetReference(ref); fp.SetValue(c['value']); fp.SetFPID(p.LIB_ID(lib,name))
        fp.SetExcludedFromBOM(False)
        if c.get('datasheet'): fp.GetField(p.FIELD_T_DATASHEET).SetText(c['datasheet'])
        fp.SetPath(p.KIID_PATH('/'+model['schematic_uuid']+'/'+c['uuid']))
        x,y,a=places[ref]; fp.SetPosition(pt(x,y)); fp.SetOrientationDegrees(a)
        fp.Value().SetVisible(False)
        for field in fp.GraphicalItems():
            if isinstance(field,p.PCB_TEXT) and field.GetText()=='${REFERENCE}': field.SetVisible(False)
        r=fp.Reference(); r.SetVisible(True); r.SetLayer(p.F_SilkS); r.SetTextSize(pt(.8,.8)); r.SetTextThickness(mm(.12))
        r.SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
        if ref.startswith('R') or ref.startswith('C') or ref.startswith('D') or ref=='F1':
            r.SetPosition(pt(x+2.4 if a==90 else x,y if a==90 else y-1.7))
        elif ref.startswith('H'): r.SetPosition(pt(x+3 if x<50 else x-3,y))
        elif ref in ['U2','U3']: r.SetPosition(pt(x,y))
        for pad in fp.Pads():
            pn=pin_nets.get((ref,pad.GetNumber()))
            if pn: pad.SetNet(nets[pn])
            elif pad.GetNumber() and ref[0]!='H': raise RuntimeError(f'No canonical net: {ref}.{pad.GetNumber()}')
        fps[ref]=fp
    rect(board,0,0,100,80,p.Edge_Cuts,.05)
    z=p.ZONE(board); z.SetLayer(p.F_Cu); z.SetIsRuleArea(True)
    z.SetDoNotAllowFootprints(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(False)
    o=z.Outline(); o.NewOutline()
    for x,y in [(36,10),(76,10),(76,28),(36,28)]: o.Append(int(mm(x)),int(mm(y)))
    board.Add(z)
    # Metal M3 screw heads/washers must not sit over traces or vias. These
    # are real copper keepouts, distinct from cosmetic component outlines.
    for hx,hy in mounting_holes():
        for layer in (p.F_Cu,p.B_Cu):
            head=p.ZONE(board);head.SetLayer(layer);head.SetIsRuleArea(True)
            head.SetDoNotAllowFootprints(False);head.SetDoNotAllowPads(False)
            head.SetDoNotAllowTracks(True);head.SetDoNotAllowVias(True);head.SetDoNotAllowZoneFills(True)
            outline=head.Outline();outline.NewOutline()
            for i in range(48):
                angle=2*math.pi*i/48
                outline.Append(int(mm(hx+3.5*math.cos(angle))),int(mm(hy+3.5*math.sin(angle))))
            board.Add(head)
    rect(board,36,10,76,28,p.Dwgs_User,.15)
    text(board,'USB RECEIVER CLEARANCE',56,17,1.2,p.Dwgs_User)
    text(board,'NO TALL PARTS  /  COPPER ALLOWED',56,20,.9,p.Dwgs_User)
    text(board,'RP2350 EXPANDABLE CARRIER V0.1',43,4,1.3)
    text(board,'3V3 LOGIC  |  NO MOTOR POWER',51,7,1)
    text(board,'ENGINEERING SAMPLE',49,79,.8)
    text(board,'EN IS NOT STO',85,26,.9)
    text(board,'3V3 SPI',87,7,.9)
    for i,(left,right) in enumerate([('3V3','GND'),('SCK','GND'),('MOSI','MISO'),('CS','EN'),('IRQ','GND')]):
        text(board,left,81,10+2.54*i,.8); text(board,right,96,10+2.54*i,.8)
    text(board,'TYPE-C',7,8,.8)
    text(board,'USB-A >',29,8,.8)
    for i,x in enumerate([11,33,55,77],1):
        text(board,['THROTTLE','BRAKE','CLUTCH','AUX'][i-1],x+5.08,60.2,1)
        for j,s in enumerate(['5V','GND','OUT']): text(board,s,x+5.08*j,77,.8)
    for s,x,y in [('BTN 01-08',36,33),('BTN 09-16',64,33),('PANEL ENC',25,35.2),
                  ('MODE',24,56.8),
                  ('PWM 2/3',78,51),('JP1 OPEN=OFF',74,64),('5V SENSOR',6,47.5)]: text(board,s,x,y,.85)
    for s,y in [('HAPTIC 1',35.5),('HAPTIC 2',47.5),('I2C 3V3',62)]: text(board,s,99,y,.85,rotation=90)
    for ref in ['J5','J6','J7','J8','J9','J10','J12','J13','JP1']:
        fp=fps[ref]
        for pad in fp.Pads():
            n=pad.GetNumber(); x,y=pad.GetPosition(); x=p.ToMM(x); y=p.ToMM(y)
            if ref in ['J5','J6']: label='G' if n=='9' else str(int(n)+(0 if ref=='J5' else 8))
            else: label={'J7':['3V3','G','A','B'],'J8':['3V3','G','SDA','SCL'],
                'J9':['3V3','G','PWM'],'J10':['3V3','G','PWM'],'J12':['SW','G'],
                'J13':['3V3','G','2','3'],'JP1':['OE','G']}[ref][int(n)-1]
            if ref=='JP1': text(board,label,x-2.5,y,.8)
            else: text(board,label,x-2.8 if ref not in ['J5','J6'] else x+2.7,y,.8)
    # Standard library model environment variables remain portable; env.ps1
    # resolves them to the bundled official STEP files for offline rendering.
    position_references(board)
    for i,pin in enumerate(['12','13','14','15'],1):
        adc=next(pad for pad in fps['U1'].Pads() if pad.GetNumber()==pin)
        cap=next(pad for pad in fps[f'C{i}'].Pads() if pad.GetNumber()=='1')
        t=p.PCB_TRACK(board); t.SetStart(adc.GetPosition()); t.SetEnd(cap.GetPosition()); t.SetWidth(mm(.25))
        t.SetLayer(p.F_Cu); t.SetNet(adc.GetNet()); board.Add(t)
    board.BuildConnectivity()
    p.SaveBoard(str(OUT/'carrier.kicad_pcb'),board)
    (OUT/'placement.json').write_text(json.dumps({r:{'x_mm':a[0],'y_mm':a[1],'rotation_deg':a[2]} for r,a in places.items()},indent=2),encoding='utf-8')
    # KiCad exports component-only keepouts as copper keepouts in Specctra.
    # Omit this one zone from the router exchange, retaining it in the PCB.
    board.Remove(z)
    p.ExportSpecctraDSN(board,str(OUT/'reports/carrier-unrouted.dsn'))
    print(f'Built {len(fps)} footprints, {len(nets)} native nets, {sum(1 for fp in fps.values() for _ in fp.Pads())} pads')
    return board

def finalize(session):
    # Always start from the canonical placement, making repeated imports safe.
    build()
    board=p.LoadBoard(str(OUT/'carrier.kicad_pcb'))
    if not p.ImportSpecctraSES(board,str(session)): raise RuntimeError('Native SES import failed')
    gnd=board.FindNet('/GND')
    for layer in [p.F_Cu,p.B_Cu]:
        z=p.ZONE(board); z.SetLayer(layer); z.SetNet(gnd); z.SetLocalClearance(mm(.2))
        z.SetPadConnection(p.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(mm(.25)); z.SetThermalReliefSpokeWidth(mm(.3))
        z.SetMinThickness(mm(.2)); o=z.Outline(); o.NewOutline()
        for x,y in [(.5,.5),(99.5,.5),(99.5,79.5),(.5,79.5)]: o.Append(int(mm(x)),int(mm(y)))
        board.Add(z)
    board.BuildConnectivity(); p.ZONE_FILLER(board).Fill(board.Zones())
    p.SaveBoard(str(OUT/'carrier.kicad_pcb'),board)
    print('Imported native SES and filled front/back ground planes')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--import-session',type=Path); args=ap.parse_args()
    if args.import_session: finalize(args.import_session)
    else: build()
