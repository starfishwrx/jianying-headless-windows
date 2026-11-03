"""Native caption alignment and line-width parameters, including drift checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import jy14_headless as j


class TextLayoutTests(unittest.TestCase):
    def test_subtitles_default_to_centered_bounded_native_wrapping(self):
        bp = j.read_json(Path(j.__file__).with_name('blueprint.json'))
        mat = deepcopy(next(m for bucket, m in bp['text']['materials'] if bucket == 'texts'))
        j.text_material(mat, {'text': '第一行\n第二行', 'subtitle': True, 'size': 8, 'bold': True})
        self.assertEqual(mat['alignment'], 1)
        self.assertEqual(mat['line_max_width'], .8)
        self.assertIs(mat['force_apply_line_max_width'], True)
        self.assertEqual(json.loads(mat['content'])['text'], '第一行\n第二行')

    def test_ordinary_titles_keep_blueprint_geometry_unless_explicit(self):
        bp = j.read_json(Path(j.__file__).with_name('blueprint.json'))
        mat = deepcopy(next(m for bucket, m in bp['text']['materials'] if bucket == 'texts'))
        original = deepcopy(mat)
        j.text_material(mat, {'text': 'Title'})
        self.assertEqual(mat.get('alignment'), original.get('alignment'))
        self.assertEqual(mat.get('line_max_width'), original.get('line_max_width'))

    def test_invalid_alignment_and_width_are_rejected_before_media_probe(self):
        for field, value in (('alignment', True), ('alignment', 3), ('max_line_width', 0),
                             ('max_line_width', float('nan')), ('max_line_width', 1.2)):
            plan = {'schema': 'jy14-headless-plan/v1', 'name': 'layout-test',
                    'canvas': {'width': 1080, 'height': 1920, 'fps': 30},
                    'tracks': [{'type': 'video', 'segments': [{'source': 'missing.mp4', 'duration_us': 1000000}]},
                               {'type': 'text', 'segments': [{'text': 'caption', 'duration_us': 1000000,
                                                              field: value}]}]}
            from unittest.mock import patch
            with self.subTest(field=field, value=value), patch.object(j, 'probe', return_value={
                    'kind':'video', 'duration_us':1000000, 'media_type':'video'}):
                with self.assertRaises((ValueError, SystemExit)):
                    j.validate_plan(plan)


if __name__ == '__main__':
    unittest.main()
