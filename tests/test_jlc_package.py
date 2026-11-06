"""Manufacturing contracts: no missing placements or changed copper at handoff."""
import csv
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/hardware'))
try:
    from package_jlc import build_smt_tables, gerber_drawing_stream
except ImportError:
    build_smt_tables = gerber_drawing_stream = None


class JlcPackageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(build_smt_tables, 'JLC manufacturing exporter must exist')
        with (ROOT / 'hardware/carrier/bom.csv').open(encoding='utf-8-sig', newline='') as f:
            self.bom = list(csv.DictReader(f))
        import json
        placement = json.loads((ROOT / 'hardware/carrier/placement.json').read_text())
        self.positions = []
        for part in self.bom:
            if part['Reference'].startswith(('R', 'C', 'D', 'F')) or part['Reference'] in ('U2', 'U3'):
                p = placement[part['Reference']]
                self.positions.append(dict(Ref=part['Reference'], Val=part['Value'],
                    Package=part['Footprint'].split(':')[1], PosX=str(p['x_mm']),
                    PosY=str(-p['y_mm']), Rot=str(p['rotation_deg']), Side='top'))

    def test_all_53_smd_parts_once_and_no_module_or_connectors(self):
        bom, cpl = build_smt_tables(self.bom, self.positions)
        actual = {r['Designator'] for r in cpl}
        expected = {f'R{i}' for i in range(1, 38)} | {f'C{i}' for i in range(1, 10)} | \
                   {f'D{i}' for i in range(1, 5)} | {'U2', 'U3', 'F1'}
        self.assertEqual(actual, expected)
        self.assertEqual(len(cpl), 53)
        self.assertEqual({ref for r in bom for ref in r['Designator'].split(',')}, expected)
        self.assertEqual(sum(int(r['Quantity']) for r in bom), 53)

    def test_coordinates_keep_native_sign_and_rotation_only_wraps(self):
        next(p for p in self.positions if p['Ref'] == 'C1').update(
            PosX='17.321000', PosY='-22.654000', Rot='-90')
        _, cpl = build_smt_tables(self.bom, self.positions)
        c1 = next(r for r in cpl if r['Designator'] == 'C1')
        self.assertEqual(float(c1['Mid X']), 17.321)
        self.assertEqual(float(c1['Mid Y']), -22.654)
        self.assertEqual(float(c1['Rotation']), 270)
        self.assertEqual(c1['Layer'], 'Top')

    def test_bom_retains_capacitor_and_exact_ic_specs(self):
        bom, _ = build_smt_tables(self.bom, self.positions)
        for ref, expected in [('U2', 'PCA9555D,118'), ('U3', 'PCA9685PW,118'),
                              ('F1', 'MF-NSMF025X-2')]:
            row = next(r for r in bom if ref in r['Designator'].split(','))
            self.assertEqual(row['Manufacturer Part'], expected)
        caps = [r for r in bom if 'C1' in r['Designator'].split(',')]
        self.assertIn('16V X7R', caps[0]['Comment'])
        self.assertEqual(caps[0]['LCSC Part #'], '')

    def test_missing_duplicate_or_unexpected_coordinates_fail(self):
        for positions in [self.positions[:-1], self.positions + [self.positions[0]],
                          self.positions + [dict(self.positions[0], Ref='U1')]]:
            with self.subTest(positions=len(positions)), self.assertRaises(ValueError):
                build_smt_tables(self.bom, positions)

    def test_invalid_positions_or_mismatched_packages_fail(self):
        for change in [dict(PosX='nan'), dict(PosY='inf'), dict(Rot='nan'),
                       dict(Side='bottom'), dict(Package='WRONG'), dict(PosX='101'),
                       dict(Val='100uF')]:
            positions = [dict(r) for r in self.positions]
            positions[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_smt_tables(self.bom, positions)

    def test_attribute_and_comment_changes_do_not_change_drawing_stream(self):
        x2 = '%TF.FileFunction,Copper,L1,Top*%\n%FSLAX46Y46*%\n%TA.AperFunction,Conductor*%\nX100Y200D01*\n%TD*%\nM02*\n'
        rs274x = 'G04 Different creation date*\n%FSLAX46Y46*%\nX100Y200D01*\nM02*\n'
        self.assertEqual(gerber_drawing_stream(x2), gerber_drawing_stream(rs274x))
        self.assertNotEqual(gerber_drawing_stream(x2),
                            gerber_drawing_stream(rs274x.replace('X100', 'X101')))


if __name__ == '__main__':
    unittest.main()
