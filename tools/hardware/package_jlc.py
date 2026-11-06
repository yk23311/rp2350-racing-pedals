"""Validate and package a JLC quoting/upload set; never submit a factory order."""
import csv
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / 'hardware/carrier'
NATIVE = ROOT / 'build/jlc-v0.1'
OUT = ROOT / 'hardware/jlc-v0.1'
DIST = ROOT / 'dist/carrier-jlc-v0.1'
LAYERS = ('gtl', 'gbl', 'gtp', 'gbp', 'gto', 'gbo', 'gts', 'gbs', 'gm1')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    if not rows:
        raise ValueError('Empty manufacturing table: ' + str(path))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def smd_parts(rows):
    libraries = ('Resistor_SMD:', 'Capacitor_SMD:', 'Diode_SMD:', 'Fuse:', 'Package_SO:')
    return {r['Reference']: r for r in rows if r['Footprint'].startswith(libraries)}


def natural_key(ref):
    match = re.fullmatch(r'([A-Z]+)(\d+)', ref)
    if not match:
        raise ValueError('Unexpected reference: ' + ref)
    return match[1], int(match[2])


def build_smt_tables(parts, positions):
    expected = smd_parts(parts)
    actual = [p['Ref'] for p in positions]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError('Native SMT positions do not match the BOM exactly')
    grouped = defaultdict(list)
    cpl = []
    for p in sorted(positions, key=lambda p: natural_key(p['Ref'])):
        ref = p['Ref']
        part = expected[ref]
        x, y, rotation = (float(p[k]) for k in ('PosX', 'PosY', 'Rot'))
        if not all(math.isfinite(n) for n in (x, y, rotation)):
            raise ValueError('Nonfinite coordinate: ' + ref)
        if not 0 <= x <= 100 or not -80 <= y <= 0 or p['Side'] != 'top':
            raise ValueError('Placement is outside the reviewed front board: ' + ref)
        if p['Package'] != part['Footprint'].split(':')[1] or p['Val'] != part['Value']:
            raise ValueError('Placement package/value mismatch: ' + ref)
        cpl.append({'Designator': ref, 'Mid X': f'{x:.6f}', 'Mid Y': f'{y:.6f}',
                    'Layer': 'Top', 'Rotation': f'{rotation % 360:.3f}'})
        grouped[(part['Value'], part['Footprint'].split(':')[1],
                 part['Manufacturer'], part['MPN'])].append(ref)
    bom = []
    for (value, footprint, manufacturer, mpn), refs in grouped.items():
        bom.append({'Comment': value, 'Designator': ','.join(refs), 'Footprint': footprint,
                    'Quantity': len(refs), 'Manufacturer': manufacturer,
                    'Manufacturer Part': mpn, 'LCSC Part #': ''})
    return bom, cpl


def gerber_drawing_stream(contents):
    """Compare all non-comment/non-attribute plot operations, including macros."""
    return '\n'.join(line.strip() for line in contents.splitlines()
                     if line.strip() and not line.strip().startswith('G04')
                     and not re.match(r'^%T[FADO]', line.strip()))


def check_native_reports():
    erc = json.loads((NATIVE / 'checks/erc.json').read_text())
    drc = json.loads((NATIVE / 'checks/drc.json').read_text())
    if any(s['violations'] for s in erc['sheets']):
        raise ValueError('ERC is not clean')
    if any(drc[k] for k in ('violations', 'unconnected_items', 'schematic_parity')):
        raise ValueError('DRC/parity is not clean')
    return erc['kicad_version']


def main():
    manifest = json.loads((BOARD / 'manifest.json').read_text(encoding='utf-8'))
    for name, item in manifest['files'].items():
        if sha((BOARD / name).read_bytes()) != item['sha256']:
            raise ValueError('Reviewed V0.1 input changed: ' + name)
    version = check_native_reports()
    parts = read_csv(BOARD / 'bom.csv')
    positions = read_csv(NATIVE / 'carrier-pos.csv')
    bom, cpl = build_smt_tables(parts, positions)
    if len(cpl) != 53:
        raise ValueError('Unexpected reviewed V0.1 SMT count')
    placement = json.loads((BOARD / 'placement.json').read_text())
    for p in cpl:
        original = placement[p['Designator']]
        if (abs(float(p['Mid X']) - original['x_mm']) > 1e-5 or
            abs(float(p['Mid Y']) + original['y_mm']) > 1e-5 or
            abs(float(p['Rotation']) - original['rotation_deg'] % 360) > 0.001):
            raise ValueError('Native position differs from reviewed placement: ' + p['Designator'])

    OUT.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / '02-BOM-SMT.csv', bom)
    write_csv(OUT / '03-CPL-SMT.csv', cpl)
    dip = []
    for part in parts:
        ref = part['Reference']
        if ref.startswith('J'):
            dip.append({'Reference': ref, 'Quantity': 1, 'Value': part['Value'],
                        'Footprint': part['Footprint'].split(':')[1], 'MPN': part['MPN'],
                        'Assembly note': 'Fit header only; NO SHUNT' if ref == 'JP1'
                                         else 'Through-hole; separate factory quote/approval'})
    dip.append({'Reference': 'U1 SOCKETS (two rows, not module)', 'Quantity': 2,
                'Value': '1x9 female socket; 2.54mm pitch; straight; module mating height to verify',
                'Footprint': 'See U1 socket assembly drawing', 'MPN': '',
                'Assembly note': 'Two female sockets only; user inserts existing RP2350 module last'})
    write_csv(OUT / '04-DIP-quote-only.csv', dip)
    shutil.copyfile(NATIVE / 'carrier-pos.csv', OUT / 'carrier-pos-kicad.csv')
    (OUT / 'checks').mkdir(exist_ok=True)
    for report in ('erc.json', 'drc.json'):
        shutil.copyfile(NATIVE / 'checks' / report, OUT / 'checks' / report)

    geometry = {}
    fabfiles = []
    for extension in LAYERS:
        path = next((NATIVE / 'gerber').glob('*.' + extension))
        original = BOARD / 'fabrication' / path.name
        text = path.read_text()
        if re.search(r'^%T[FADO]', text, re.MULTILINE):
            raise ValueError('JLC output still contains active X2 attributes: ' + path.name)
        stream = gerber_drawing_stream(text)
        if stream != gerber_drawing_stream(original.read_text()):
            raise ValueError('Manufacturing drawing changed: ' + path.name)
        geometry[path.name] = {'drawing_sha256': sha(stream.encode()),
                               'rs274x_sha256': sha(path.read_bytes()),
                               'source_x2_sha256': sha(original.read_bytes())}
        fabfiles.append(path)
    fabfiles.extend(BOARD / 'fabrication' / n for n in ('carrier-PTH.drl', 'carrier-NPTH.drl'))
    fabzip = DIST / '01-PCB-Gerber-RS274X.zip'
    with zipfile.ZipFile(fabzip, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in fabfiles:
            archive.write(path, path.name)

    report = {'revision': 'V0.1 JLC quote/upload set', 'kicad': version,
              'source_board_sha256': sha((BOARD / 'carrier.kicad_pcb').read_bytes()),
              'source_manifest_sha256': sha((BOARD / 'manifest.json').read_bytes()),
              'erc_violations': 0, 'drc_violations': 0, 'unconnected': 0,
              'schematic_mismatch': 0, 'smt_placements': len(cpl), 'smt_bom_groups': len(bom),
              'dip_items_per_board': sum(r['Quantity'] for r in dip),
              'drills_copied_without_changes': True, 'gerber_geometry_equivalent': geometry,
              'coordinates': 'mm, native KiCad X/Y with Y negative; rotation normalized 0..360',
              'factory_stock_matched': False, 'factory_rotation_reviewed': False,
              'factory_dfm_approved': False, 'dip_assembly_quoted': False,
              'order_submitted': False, 'manufactured': False, 'powered_tested': False}
    (OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    # Human-maintained README and socket diagram accompany every regenerated set.
    for name in ('README.md', '05-assembly-notes.md', '06-module-sockets.svg'):
        if not (OUT / name).is_file():
            raise ValueError('Missing assembly instructions: ' + name)
    payload = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    (OUT / 'SHA256SUMS.txt').write_text('\n'.join(
        f'{sha(p.read_bytes())}  {p.relative_to(OUT).as_posix()}' for p in payload) + '\n')
    for path in OUT.glob('*.csv'):
        shutil.copyfile(path, DIST / path.name)
    for name in ('README.md', '05-assembly-notes.md', '06-module-sockets.svg'):
        shutil.copyfile(OUT / name, DIST / name)
    fullzip = DIST / 'carrier-jlc-v0.1-order-files.zip'
    with zipfile.ZipFile(fullzip, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(fabzip, fabzip.name)
        for path in payload + [OUT / 'SHA256SUMS.txt']:
            archive.write(path, path.relative_to(OUT).as_posix())
        for name in ('carrier-assembly-top.svg', 'carrier-3d-top.png', 'carrier-schematic.pdf'):
            archive.write(BOARD / 'previews' / name, 'reference/' + name)
    for path in (fabzip, fullzip):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP CRC failed: ' + path.name)
    with zipfile.ZipFile(fabzip) as archive:
        if any(archive.read(p.name) != p.read_bytes() for p in fabfiles):
            raise ValueError('PCB ZIP payload mismatch')
    (DIST / 'SHA256SUMS.txt').write_text('\n'.join(
        f'{sha(p.read_bytes())}  {p.name}' for p in (fabzip, fullzip)) + '\n')
    print(f'Checked {len(cpl)} SMT placements, {len(bom)} BOM groups, 9 equivalent Gerber layers, 2 original drill files.')
    print(f'DIP quote only: {report["dip_items_per_board"]} parts (including two U1 sockets).')
    print('Stock, factory rotation/DFM, DIP quote, order and hardware tests remain unconfirmed.')
    print(fullzip)


if __name__ == '__main__':
    main()
