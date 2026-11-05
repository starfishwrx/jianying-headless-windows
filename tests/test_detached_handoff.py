from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import jy14_headless as j


class DetachedHandoffTests(unittest.TestCase):
    def test_standard_unc_excludes_windows_device_namespaces(self):
        self.assertTrue(j.standard_unc(r'\\server\share\folder'))
        self.assertTrue(j.standard_unc(r'\\10.0.0.1\share\folder'))
        for value in (r'D:\folder', r'\\?\D:\folder', r'\\.\D:\folder',
                      r'\\?\UNC\server\share', r'\\server', 'relative', '\\\\server\\share\n'):
            with self.subTest(value=value):
                self.assertFalse(j.standard_unc(value))

    def test_default_target_stays_in_existing_library(self):
        target, root = j.build_target({'name': 'case'})
        self.assertEqual(target, j.nd.DRAFT_ROOT / 'case')
        self.assertEqual(root, j.nd.DRAFT_ROOT)

    def test_detached_publish_fails_before_runtime_or_home_mutation(self):
        with tempfile.TemporaryDirectory() as raw, patch.object(j.nd, 'helper') as helper:
            with self.assertRaisesRegex(ValueError, 'cannot publish'):
                j.publish(raw, str(Path(raw) / 'audit'),
                    verify_build_fn=lambda _: {'detached_root': r'\\server\share'})
            helper.assert_not_called()
            self.assertEqual(list(Path(raw).iterdir()), [])

    def test_bold_is_explicit_in_native_structured_text(self):
        import json
        material = deepcopy(j.blueprint()['text']['materials'][0][1])
        # Select the actual text material without writing any draft JSON.
        material = deepcopy(next(m for bucket, m in j.blueprint()['text']['materials'] if bucket == 'texts'))
        j.text_material(material, {'text': '验证粗体', 'bold': True})
        styles = json.loads(material['content'])['styles']
        self.assertTrue(styles and all(s['bold'] is True for s in styles))
        j.text_material(material, {'text': '验证常规', 'bold': False})
        self.assertTrue(all(s['bold'] is False for s in json.loads(material['content'])['styles']))


if __name__ == '__main__':
    unittest.main()
