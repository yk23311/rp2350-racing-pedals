"""Package the checked engineering sample; never order, publish or flash it."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / 'hardware/carrier'
OUT = ROOT / 'dist/carrier-v0.1'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def project_files():
    return sorted(p for p in BOARD.rglob('*') if p.is_file()
                  and p.suffix not in ('.kicad_prl', '.lck')
                  and '__pycache__' not in p.parts
                  and p.name not in ('manifest.json', 'SHA256SUMS.txt'))


def main():
    drc = json.loads((BOARD / 'reports/drc.json').read_text(encoding='utf-8'))
    erc = json.loads((BOARD / 'reports/erc.json').read_text(encoding='utf-8'))
    if any(drc[key] for key in ('violations', 'unconnected_items', 'schematic_parity')):
        raise RuntimeError('Native PCB checks are not clean')
    if any(sheet['violations'] for sheet in erc['sheets']):
        raise RuntimeError('Native schematic checks are not clean')
    summary = json.loads((BOARD / 'reports/pcb-summary.json').read_text(encoding='utf-8'))
    fab = sorted(p for p in (BOARD / 'fabrication').iterdir() if p.is_file())
    required = ('carrier-F_Cu.gtl', 'carrier-B_Cu.gbl', 'carrier-Edge_Cuts.gm1',
                'carrier-F_Mask.gts', 'carrier-B_Mask.gbs', 'carrier-PTH.drl',
                'carrier-NPTH.drl', 'carrier-job.gbrjob')
    if not all((BOARD / 'fabrication' / name).is_file() for name in required):
        raise RuntimeError('Manufacturing layers or drill files are missing')
    files = project_files()
    metadata = {
        'revision': 'V0.1 engineering sample', 'design_date': '2026-11-06',
        'manufactured': False, 'powered_tested': False, 'motor_tested': False,
        'motor_candidate': 'MiGE 90ST-M02430', 'servo_driver_selected': False,
        'motor_power_stage_included': False, 'firmware_modified': False,
        'validation': {'kicad': drc['kicad_version'], 'erc_violations': 0,
                       'drc_violations': 0, 'unconnected': 0, 'schematic_mismatch': 0},
        'board': summary,
        'files': {str(p.relative_to(BOARD)).replace('\\', '/'): {
            'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())} for p in files},
    }
    (BOARD / 'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    checks = [f'{digest(p.read_bytes())}  {p.relative_to(BOARD).as_posix()}'
              for p in files + [BOARD / 'manifest.json']]
    (BOARD / 'SHA256SUMS.txt').write_text('\n'.join(checks) + '\n', encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)

    fabzip = OUT / 'carrier-v0.1-fabrication.zip'
    with zipfile.ZipFile(fabzip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in fab:
            archive.write(path, path.name)
        archive.writestr('SHA256SUMS.txt', '\n'.join(
            f'{digest(p.read_bytes())}  {p.name}' for p in fab) + '\n')
    sourcezip = OUT / 'carrier-v0.1-project.zip'
    extras = [*sorted((ROOT / 'hardware/reference').glob('*')),
              *sorted((ROOT / 'tools/hardware').glob('*.py')),
              *sorted((ROOT / 'tools/hardware').glob('*.ps1')),
              *sorted((ROOT / 'tests').glob('test_carrier_*.py')),
              ROOT / 'docs/reports/19-expandable-carrier-pcb.md',
              ROOT / 'docs/superpowers/specs/2026-11-06-expandable-carrier-design.md',
              ROOT / 'docs/superpowers/plans/2026-11-06-expandable-carrier-plan.md']
    with zipfile.ZipFile(sourcezip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files + [BOARD / 'manifest.json', BOARD / 'SHA256SUMS.txt'] + extras:
            if path.is_file():
                archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr('START_HERE.md',
            '# RP2350 carrier V0.1\n\nOpen hardware/carrier/carrier.kicad_pro in KiCad 10.\n'
            'Read hardware/carrier/README.md and motor-notes.md before assembly.\n'
            'Engineering sample only: not manufactured, powered or motor tested.\n'
            'Servo driver daughtercard and motor power stage are not included.\n')
    for path in (sourcezip, fabzip):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('ZIP CRC check failed: ' + str(path))
    with zipfile.ZipFile(fabzip) as archive:
        for path in fab:
            if archive.read(path.name) != path.read_bytes():
                raise RuntimeError('Manufacturing ZIP differs: ' + path.name)
    for line in checks:
        expected, name = line.split('  ', 1)
        if digest((BOARD / name).read_bytes()) != expected:
            raise RuntimeError('Project file hash differs: ' + name)
    (OUT / 'SHA256SUMS.txt').write_text('\n'.join(
        f'{digest(p.read_bytes())}  {p.name}' for p in (sourcezip, fabzip)) + '\n', encoding='utf-8')
    print(f'Checked {len(files)} project files; ZIP CRC, hashes and manufacturing payloads match.')
    for path in (sourcezip, fabzip):
        print(path.name, path.stat().st_size, digest(path.read_bytes()))


if __name__ == '__main__':
    main()
