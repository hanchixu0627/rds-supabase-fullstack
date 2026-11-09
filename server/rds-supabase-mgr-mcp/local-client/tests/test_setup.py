import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('setup_client', Path(__file__).parents[1]/'setup_client.py')
client=importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.bundle=self.base/'bundle'
        (self.bundle/'skill'/'references').mkdir(parents=True)
        (self.bundle/'skill'/'SKILL.md').write_text('skill')
        (self.bundle/'skill'/'references'/'flow.md').write_text('flow')
        self.root=self.base/'安装 with spaces'
        self.root.mkdir()
        self.calls=[]
    def execute(self,*args,**kwargs):self.calls.append((args,kwargs))
    def install(self,execute=None):
        return client.setup(self.bundle,self.root,self.root/'runtime'/'Scripts'/'python.exe',self.bundle/'uv.exe',execute or self.execute)
    def test_defaults_readonly_and_no_secrets(self):
        r=self.install()
        s=r['config']['mcpServers']['huaweicloud-supabase']
        self.assertEqual(s['env']['SUPABASE_ENABLE_WRITES'],'false')
        self.assertEqual(s['env']['HUAWEICLOUD_MCP_READ_ONLY'],'true')
        self.assertEqual(s['env']['SUPABASE_STATE_FILE'],str(self.root/'state'/'plans.sqlite3'))
        self.assertNotIn('HUAWEICLOUD_ACCESS_KEY',s['env'])
        self.assertTrue((self.root/'workspace'/'.claude'/'skills'/'huaweicloud-supabase'/'references'/'flow.md').exists())
    def test_failed_diagnostics_never_activates(self):
        def fail(args,**kwargs):
            if 'offline' in args:raise RuntimeError('diagnostic failed')
        with self.assertRaises(RuntimeError):self.install(fail)
        self.assertFalse((self.root/'workspace'/'.mcp.json').exists())
        self.assertFalse((self.root/'installed.json').exists())
    def test_second_launch_reuses_runtime_and_preserves_ledger(self):
        self.install()
        ledger=self.root/'state'/'plans.sqlite3'
        ledger.write_bytes(b'opaque ledger')
        self.calls.clear()
        self.install()
        self.assertEqual(self.calls,[])
        self.assertEqual(ledger.read_bytes(),b'opaque ledger')
    def test_existing_unowned_config_never_overwritten(self):
        w=self.root/'workspace';w.mkdir()
        (w/'.mcp.json').write_text('original')
        with self.assertRaises(ValueError):self.install()
        self.assertEqual((w/'.mcp.json').read_text(),'original')
        self.assertEqual(self.calls,[])
    def test_user_config_change_is_not_reset_or_launched(self):
        self.install()
        p=self.root/'workspace'/'.mcp.json'
        p.write_text('modified')
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(p.read_text(),'modified')
    def test_cloud_credentials_not_passed_to_offline_diagnostic(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{'HUAWEICLOUD_ACCESS_KEY':'secret','SUPABASE_ENABLE_WRITES':'true'}):
            self.install()
        for args,kw in self.calls:
            self.assertNotIn('HUAWEICLOUD_ACCESS_KEY',kw['env'])
            self.assertEqual(kw['env']['SUPABASE_ENABLE_WRITES'],'false')
    def test_partial_skill_write_does_not_replace_existing_user_files(self):
        w=self.root/'workspace'/'.claude'/'skills'/'huaweicloud-supabase'
        w.mkdir(parents=True);(w/'SKILL.md').write_text('user')
        with self.assertRaises(ValueError):self.install()
        self.assertEqual((w/'SKILL.md').read_text(),'user')

if __name__=='__main__':unittest.main()
