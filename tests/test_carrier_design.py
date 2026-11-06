"""Electrical contract tests, independent of schematic drawing coordinates."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'hardware/carrier/design.json'


class CarrierDesignTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODEL.exists(), 'carrier electrical model must exist')
        self.model = json.loads(MODEL.read_text(encoding='utf-8'))
        self.c = self.model['components']

    def test_module_assignment_and_no_motor_supply(self):
        expected = ['I2C_SDA', 'I2C_SCL', 'ENC_A', 'ENC_B', 'SPI_MISO',
                    'SPI_CS', 'SPI_SCK', 'SPI_MOSI', 'FFB_EN_MCU',
                    'FFB_IRQ_N', 'MODE_N', 'ADC_THROTTLE', 'ADC_BRAKE',
                    'ADC_CLUTCH', 'ADC_AUX', '+3V3', 'GND', '+5V_USB']
        self.assertEqual(self.c['U1']['pins'], {str(i+1): n for i, n in enumerate(expected)})
        self.assertNotIn('MOTOR_VBUS', self.model['nets'])

    def test_four_filtered_dividers(self):
        for i, name in enumerate(['THROTTLE', 'BRAKE', 'CLUTCH', 'AUX'], 1):
            raw, adc = f'ANALOG_{name}', f'ADC_{name}'
            self.assertEqual(self.c[f'J{i}']['pins'], {'1': '+5V_SENSOR', '2': 'GND', '3': raw})
            self.assertEqual(self.c[f'R{2*i-1}']['pins'], {'1': raw, '2': adc})
            self.assertEqual(self.c[f'R{2*i}']['pins'], {'1': adc, '2': 'GND'})
            for ref in [f'R{2*i-1}', f'R{2*i}']:
                self.assertEqual(self.c[ref]['value'], '10k 1%')
            self.assertEqual(self.c[f'C{i}']['pins'], {'1': adc, '2': 'GND'})
            self.assertEqual(self.c[f'C{i}']['value'], '100nF 16V X7R')
            self.assertEqual(self.c[f'D{i}']['pins'], {'1': raw, '2': 'GND'})

    def test_all_sixteen_buttons_have_pullups(self):
        gpio = list(range(4, 12)) + list(range(13, 21))
        for i, pin in enumerate(gpio, 1):
            net = f'BTN{i:02}'
            self.assertEqual(self.c['U2']['pins'][str(pin)], net)
            self.assertEqual(self.c[f'R{i+8}']['pins'], {'1': '+3V3', '2': net})
            jack = self.c['J5' if i <= 8 else 'J6']['pins']
            self.assertEqual(jack[str((i-1)%8+1)], net)
            self.assertEqual(jack['9'], 'GND')

    def test_default_disable_and_addresses(self):
        self.assertEqual(self.c['R30']['pins'], {'1': 'FFB_EN_MCU', '2': 'FFB_EN'})
        self.assertEqual(self.c['R31']['pins'], {'1': 'FFB_EN', '2': 'GND'})
        self.assertEqual(self.c['R36']['pins'], {'1': '+3V3', '2': 'PWM_OE_N'})
        self.assertEqual(self.c['JP1']['pins'], {'1': 'PWM_OE_N', '2': 'GND'})
        self.assertEqual(self.c['U3']['pins']['25'], 'GND')
        self.assertEqual(self.model['i2c_addresses'], {'U2': '0x20', 'U3': '0x40', 'U3_allcall': '0x70'})
        for pin in ['2', '3', '21']:
            self.assertEqual(self.c['U2']['pins'][pin], 'GND')
        for pin in ['1', '2', '3', '4', '5', '24']:
            self.assertEqual(self.c['U3']['pins'][pin], 'GND')

    def test_model_complete_and_sensor_supply_fused(self):
        self.assertEqual(self.c['F1']['pins'], {'1': '+5V_USB', '2': '+5V_SENSOR'})
        for ref, part in self.c.items():
            self.assertIn(':', part['symbol'], ref)
            self.assertIn(':', part['footprint'], ref)
            for net in part['pins'].values():
                if net is not None:
                    self.assertIn(net, self.model['nets'], ref)
        for ref in ('J7', 'J8', 'J9', 'J10', 'J11', 'J12', 'J13'):
            self.assertNotIn('+5V_USB', self.c[ref]['pins'].values())
            self.assertNotIn('+5V_SENSOR', self.c[ref]['pins'].values())

    def test_native_kicad_netlist_matches_contract(self):
        path = ROOT / 'hardware/carrier/carrier.net'
        self.assertTrue(path.exists(), 'Export real netlist with kicad-cli first')
        netlist = ET.parse(path).getroot()
        actual_parts = {p.attrib['ref']: p for p in netlist.find('components')}
        self.assertEqual(set(actual_parts), set(self.c))
        actual = {}
        for net in netlist.find('nets'):
            for node in net.findall('node'):
                actual[(node.attrib['ref'], node.attrib['pin'])] = net.attrib['name'].removeprefix('/')
        for ref, part in self.c.items():
            self.assertEqual(actual_parts[ref].findtext('value'), part['value'], ref)
            self.assertEqual(actual_parts[ref].findtext('footprint'), part['footprint'], ref)
            for pin, net in part['pins'].items():
                if net is None:
                    self.assertTrue(actual[(ref,pin)].startswith('unconnected-'), (ref,pin))
                else:
                    self.assertEqual(actual[(ref,pin)], net, (ref,pin))


if __name__ == '__main__':
    unittest.main()
