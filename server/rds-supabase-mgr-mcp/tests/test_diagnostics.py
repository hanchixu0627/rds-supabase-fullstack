"""The workstation CLI must be usable without contacting a cloud service."""
import json
import os
import subprocess
import sys
import unittest


class DiagnosticsTests(unittest.TestCase):
    def run_cli(self, *args, config=None):
        env = {k:v for k,v in os.environ.items() if not k.startswith(('HUAWEICLOUD_', 'SUPABASE_'))}
        env.update(config or {})
        return subprocess.run([sys.executable,'-m','mcp_server_supabase.diagnostics',*args],
                              env=env,capture_output=True,text=True,timeout=30)

    def test_check_missing_configuration_does_not_echo_values(self):
        result = self.run_cli('check')
        self.assertEqual(result.returncode,2)
        report = json.loads(result.stdout)
        self.assertFalse(report['cloud_ready'])
        self.assertFalse(report['network_attempted'])

    def test_config_check_validates_without_network(self):
        result = self.run_cli('check', config={'SUPABASE_RDS_ENDPOINT':'https://example.invalid',
             'HUAWEICLOUD_PROJECT_ID':'test-project','HUAWEICLOUD_AUTH_TOKEN':'private-marker'})
        self.assertEqual(result.returncode,0)
        report=json.loads(result.stdout)
        self.assertTrue(report['cloud_ready'])
        self.assertFalse(report['network_attempted'])
        self.assertNotIn('private-marker',result.stdout+result.stderr)
        self.assertNotIn('example.invalid',result.stdout+result.stderr)

    def test_invalid_url_and_header_rejected_locally(self):
        result = self.run_cli('check',config={'SUPABASE_RDS_ENDPOINT':'https://user:private-marker@example.invalid',
            'HUAWEICLOUD_PROJECT_ID':'test-project','HUAWEICLOUD_AUTH_TOKEN':'private-marker\n'})
        report=json.loads(result.stdout)
        self.assertEqual(result.returncode,2)
        self.assertFalse(report['checks']['endpoint_valid'])
        self.assertFalse(report['checks']['token_present_and_valid'])
        self.assertNotIn('private-marker',result.stdout+result.stderr)

    def test_readonly_requires_explicit_cloud_opt_in(self):
        result=self.run_cli('readonly')
        self.assertEqual(result.returncode,2)
        self.assertFalse(json.loads(result.stdout)['network_attempted'])

    def test_offline_ignores_inherited_cloud_credentials(self):
        result=self.run_cli('offline',config={'SUPABASE_RDS_ENDPOINT':'https://example.invalid',
            'HUAWEICLOUD_AUTH_TOKEN':'private-marker','SUPABASE_ENABLE_WRITES':'true',
            'HUAWEICLOUD_MCP_READ_ONLY':'true'})
        self.assertEqual(result.returncode,0,result.stdout)
        report=json.loads(result.stdout)
        self.assertTrue(report['passed'])
        self.assertFalse(report['network_attempted'])
        self.assertGreaterEqual(len(report['checks']),5)
        self.assertNotIn('private-marker',result.stdout+result.stderr)

    def test_sdk_check_requires_ak_sk_not_token(self):
        config={'SUPABASE_TRANSPORT':'sdk_core','SUPABASE_RDS_ENDPOINT':'https://example.invalid',
            'HUAWEICLOUD_PROJECT_ID':'test-project','HUAWEICLOUD_ACCESS_KEY':'private-ak',
            'HUAWEICLOUD_SECRET_KEY':'private-sk','HUAWEICLOUD_SECURITY_TOKEN':'private-sts'}
        result=self.run_cli('check',config=config)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertNotIn('private-',result.stdout+result.stderr)
        self.assertFalse(json.loads(result.stdout)['network_attempted'])
        config.pop('HUAWEICLOUD_SECRET_KEY')
        self.assertEqual(self.run_cli('check',config=config).returncode,2)
