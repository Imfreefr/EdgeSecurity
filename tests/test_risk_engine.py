import json
import unittest
from pathlib import Path
from backend.services.risk_engine import assess_risk


class RiskEngineTests(unittest.TestCase):
    def test_shared_cases(self):
        cases = json.loads(Path('tests/risk-cases.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(case=case['name']):
                result = assess_risk(case['detections'], frame_width=case['width'])
                self.assertEqual(result['level'], case['level'])
                self.assertEqual(len(result['pairs']), case['pairs'])
                if 'reference_gap' in case:
                    self.assertEqual(result['pairs'][0]['gap_reference_pixels'], case['reference_gap'])

    def test_invalid_dimensions(self):
        for width in (0, -1, float('nan'), float('inf'), '640'):
            with self.assertRaises(ValueError):
                assess_risk([], frame_width=width)


if __name__ == '__main__':
    unittest.main()
