import unittest
from mcp_server_supabase.service.contracts import ssl_body, api_key_query, accepted_job

class ContractTests(unittest.TestCase):
    def test_disable_explicit_null(self):
        self.assertEqual(ssl_body(False), {'enable_ssl': False, 'cert_id': None})
        with self.assertRaises(ValueError):
            ssl_body(False, 'cert-123')

    def test_certificate_validation(self):
        self.assertEqual(ssl_body(True, 'cert-123')['cert_id'], 'cert-123')
        for bad in (None, '', '../secret', 'x'*65):
            with self.assertRaises(ValueError):
                ssl_body(True, bad)
        with self.assertRaises(ValueError):
            ssl_body('false')

    def test_pagination(self):
        self.assertEqual(api_key_query()['limit'], 10)
        for kwargs in ({'limit':0}, {'limit':101}, {'offset':-1}, {'limit':True}, {'status':'unknown'}, {'key_type':'unknown'}, {'sort_key':'password'}):
            with self.assertRaises(ValueError):
                api_key_query(**kwargs)
        self.assertEqual(api_key_query(key_type='secret')['type'], 'secret')

    def test_acceptance_is_not_completion(self):
        self.assertEqual(accepted_job(202, {'job_id':'job-1', 'api_key':'sensitive'}) , {'status':'accepted','job_id':'job-1','complete':False})
        for status, body in ((200, {'job_id':'j'}), (202, {}), (202, {'job_id':None})):
            with self.assertRaises(ValueError):
                accepted_job(status, body)
