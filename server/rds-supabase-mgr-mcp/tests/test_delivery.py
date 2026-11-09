import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

class DeliveryTests(unittest.TestCase):
    def load(self):
        spec=importlib.util.spec_from_file_location('delivery',Path(__file__).parents[1]/'scripts'/'verify_delivery.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_environment_matrix_is_not_an_acceptance_claim(self):
        m=self.load()
        self.assertTrue(m.target_match('win32','AMD64',(3,12),64))
        for args in [('darwin','arm64',(3,12),64),('win32','ARM64',(3,12),64),('win32','AMD64',(3,11),64),('win32','AMD64',(3,12),32)]:
            self.assertFalse(m.target_match(*args))

    def test_manifest_rejects_changes_missing_and_unsafe_paths(self):
        m=self.load()
        with tempfile.TemporaryDirectory(prefix='验证 space ') as tmp:
            root=Path(tmp);file=root/'a.txt';file.write_text('good')
            digest=hashlib.sha256(file.read_bytes()).hexdigest()
            manifest=root/'SHA256SUMS.txt';manifest.write_text(digest+'  a.txt\n')
            self.assertEqual(m.verify_files(root),1)
            file.write_text('bad')
            with self.assertRaises(ValueError):m.verify_files(root)
            file.unlink()
            with self.assertRaises(ValueError):m.verify_files(root)
            manifest.write_text(digest+'  ../a.txt\n')
            with self.assertRaises(ValueError):m.verify_files(root)
