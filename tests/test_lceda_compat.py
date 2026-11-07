"""Compatibility copy must keep circuitry and all non-net board geometry."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/hardware'))
from build_schematic import parse
try:
    from prepare_lceda_compat import compatible_board, compatible_schematic
except ImportError:
    compatible_board=compatible_schematic=None


def children(node,tag):
    return [x for x in node if isinstance(x,list) and x and x[0]==tag]


class LcedaCompatTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(compatible_board,'LCEDA compatibility generator must exist')

    def test_network_table_resolves_pads_tracks_vias_and_copper(self):
        text='''(kicad_pcb (version 20260206)
        (footprint "R" (property "Reference" "R1") (property "Value" "10k")
          (pad "1" smd rect (net "/GND")) (pad "2" smd rect (net "/ADC")))
        (segment (start 1 2) (end 3 4) (net "/ADC"))
        (via (at 3 4) (net "/GND"))
        (zone (net "/GND") (polygon (pts (xy 0 0) (xy 4 0) (xy 4 4)))))'''
        board=parse(compatible_board(text))
        table={int(n[1]):n[2] for n in children(board,'net')}
        self.assertEqual(set(table.values()),{'""','"/GND"','"/ADC"'})
        fp=children(board,'footprint')[0]
        for pad in children(fp,'pad'):
            n=children(pad,'net')[0]
            self.assertEqual(n[2],table[int(n[1])])
        self.assertEqual(table[int(children(children(board,'segment')[0],'net')[0][1])],'"/ADC"')
        zone=children(board,'zone')[0]
        self.assertEqual(children(zone,'net_name')[0][1],'"/GND"')
        self.assertEqual(children(board,'version'),[['version','20260206']])

    def test_reference_and_value_are_per_instance_legacy_text(self):
        text='''(kicad_pcb (version 20260206)
        (footprint "C" (property "Reference" "C7" (at 1 2 0) (layer "F.SilkS"))
        (property "Value" "4.7uF 10V X7R" (at 3 4 0) (layer "F.Fab"))))'''
        b=parse(compatible_board(text));fp=children(b,'footprint')[0]
        self.assertEqual(children(fp,'fp_text'),[
            ['fp_text','reference','"C7"',['at','1','2','0'],['layer','"F.SilkS"']],
            ['fp_text','value','"4.7uF 10V X7R"',['at','3','4','0'],['layer','"F.Fab"']]])

    def test_other_board_fields_and_all_geometry_remain_exact(self):
        text='''(kicad_pcb (version 20260206) (general (thickness 1.6))
        (layers (0 "F.Cu" signal) (2 "B.Cu" signal))
        (segment (start 1 2) (end 8 9) (width 0.25) (layer "F.Cu") (uuid "abc")))'''
        original=parse(text);new=parse(compatible_board(text))
        self.assertEqual([n for n in new if not(isinstance(n,list) and n[0]=='net')],original)

    def test_real_board_reference_value_pairs_are_all_preserved(self):
        text=(ROOT/'hardware/carrier/carrier.kicad_pcb').read_text(encoding='utf-8')
        source=parse(text);target=parse(compatible_board(text))
        expected={}
        for fp in children(source,'footprint'):
            p={n[1]:n[2] for n in children(fp,'property')}
            expected[p['"Reference"']]=p['"Value"']
        actual={}
        for fp in children(target,'footprint'):
            p={n[1]:n[2] for n in children(fp,'fp_text') if n[1] in ('reference','value')}
            actual[p['reference']]=p['value']
        self.assertEqual(len(actual),72)
        self.assertEqual(actual,expected)

    def test_schematic_removes_only_erc_marker_and_preserves_72_parts(self):
        text=(ROOT/'hardware/carrier/carrier.kicad_sch').read_text(encoding='utf-8')
        source=parse(text);target=parse(compatible_schematic(text))
        original=[n for n in children(source,'symbol') if children(n,'lib_id')[0][1]!='"power:PWR_FLAG"']
        self.assertEqual(children(target,'symbol'),original)
        self.assertEqual(len(original),72)
        self.assertEqual(len(children(source,'wire'))-len(children(target,'wire')),1)
        self.assertEqual(len(children(source,'label'))-len(children(target,'label')),1)
        libs=children(target,'lib_symbols')[0]
        self.assertFalse(any(n[1]=='"power:PWR_FLAG"' for n in children(libs,'symbol')))

    def test_gnd_pin_erc_type_is_output_without_changing_pin_number_or_name(self):
        text=(ROOT/'hardware/carrier/carrier.kicad_sch').read_text(encoding='utf-8')
        target=parse(compatible_schematic(text));libs=children(target,'lib_symbols')[0]
        module=next(n for n in children(libs,'symbol') if n[1]=='"Carrier:Waveshare_RP2350_USB_A"')
        pins=[pin for sub in children(module,'symbol') for pin in children(sub,'pin')]
        gnd=next(p for p in pins if children(p,'number')[0][1]=='"17"')
        self.assertEqual(gnd[1],'power_out')
        self.assertEqual(children(gnd,'name')[0][1],'"GND"')


if __name__=='__main__':
    unittest.main()
