"""Prepare a separate indexed-net import copy, without changing the approved CAD."""
import copy
import json
from pathlib import Path
import shutil
import zipfile
from build_schematic import parse, sexpr, q, unq, uid, children, child

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'hardware/carrier'
OUT=ROOT/'hardware/lceda-compat'


def compatible_board(text):
    board=parse(text)
    if board[0]!='kicad_pcb' or children(board,'net'):
        raise ValueError('Expected the reviewed KiCad10 named-net board, not an indexed/mixed file')
    names=set()
    def collect(node):
        for item in node[1:]:
            if not isinstance(item,list):
                continue
            if item[0]=='net':
                if len(item)!=2 or not item[1].startswith('"'):
                    raise ValueError('Unexpected net representation')
                names.add(item[1])
            else:
                collect(item)
    collect(board)
    codes={'""':0}
    codes.update({name:i for i,name in enumerate(sorted(names-{'""'}),1)})
    def rewrite(node):
        for i,item in enumerate(node[1:],1):
            if not isinstance(item,list):
                continue
            if item[0]=='net':
                name=item[1]
                node[i]=['net',str(codes[name]),name] if node[0]=='pad' else ['net',str(codes[name])]
                if node[0]=='zone':
                    node.append(['net_name',name])
            else:
                rewrite(item)
        if node[0]=='footprint':
            for i,item in enumerate(node[1:],1):
                if isinstance(item,list) and item[0]=='property' and item[1] in ('"Reference"','"Value"'):
                    node[i]=['fp_text',unq(item[1]).lower(),*item[2:]]
    rewrite(board)
    insertion=next((i for i,n in enumerate(board) if isinstance(n,list) and n[0]=='footprint'),len(board))
    board[insertion:insertion]=[['net',str(code),name] for name,code in codes.items()]
    return sexpr(board)+'\n'


def ground_output(module):
    count=0
    for body in children(module,'symbol'):
        for pin in children(body,'pin'):
            if child(pin,'number')[1]=='"17"' and child(pin,'name')[1]=='"GND"':
                pin[1]='power_out'
                count+=1
    if count!=1:
        raise ValueError('Expected exactly one module ground pin')


def compatible_schematic(text):
    sheet=parse(text)
    if sheet[0]!='kicad_sch':
        raise ValueError('Expected schematic')
    flag=[n for n in children(sheet,'symbol') if child(n,'lib_id')[1]=='"power:PWR_FLAG"']
    if len(flag)!=1 or child(flag[0],'uuid')[1]!=q(uid('ground_power_flag')):
        raise ValueError('Unexpected power declaration; refusing generic symbol removal')
    remove_ids={q(uid(k)) for k in ('ground_power_flag','ground_flag_wire','ground_flag_label')}
    sheet=[n for n in sheet if not(isinstance(n,list) and children(n,'uuid') and child(n,'uuid')[1] in remove_ids)]
    lib=child(sheet,'lib_symbols')
    lib[:]=[n for n in lib if not(isinstance(n,list) and n[0]=='symbol' and n[1]=='"power:PWR_FLAG"')]
    module=next(n for n in children(lib,'symbol') if n[1]=='"Carrier:Waveshare_RP2350_USB_A"')
    ground_output(module)
    return sexpr(sheet)+'\n'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('carrier.kicad_pro','sym-lib-table','fp-lib-table'):
        shutil.copyfile(SOURCE/name,OUT/name)
    for folder in ('Carrier.pretty','3d'):
        for p in (SOURCE/folder).iterdir():
            if p.is_file():
                (OUT/folder).mkdir(exist_ok=True)
                shutil.copyfile(p,OUT/folder/p.name)
    board=compatible_board((SOURCE/'carrier.kicad_pcb').read_text(encoding='utf-8'))
    schematic=compatible_schematic((SOURCE/'carrier.kicad_sch').read_text(encoding='utf-8'))
    library=parse((SOURCE/'Carrier.kicad_sym').read_text(encoding='utf-8'))
    module=next(n for n in children(library,'symbol') if n[1]=='"Waveshare_RP2350_USB_A"')
    ground_output(module)
    (OUT/'carrier.kicad_pcb').write_text(board,encoding='utf-8')
    (OUT/'carrier.kicad_sch').write_text(schematic,encoding='utf-8')
    (OUT/'Carrier.kicad_sym').write_text(sexpr(library)+'\n',encoding='utf-8')
    print('Prepared separate indexed-net and legacy field import copy:',OUT)
    print('Original CAD untouched. Run native equivalence/ERC/DRC and manufacturing checks before packing.')


if __name__=='__main__':
    main()
