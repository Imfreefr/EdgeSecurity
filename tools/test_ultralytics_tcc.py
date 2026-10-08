import unittest
from unittest.mock import Mock, patch
from ultralytics_tcc import Platform, access_report


class PlatformTests(unittest.TestCase):
    def test_missing_key_fails_without_network(self):
        with patch('ultralytics_tcc.build_opener') as opener:
            with self.assertRaisesRegex(ValueError, 'Ultralytics key'):
                Platform(key='')
            opener.assert_not_called()

    def test_contract_checked_and_resources_validated(self):
        with patch.object(Platform, '_get', return_value={'paths': {'/api/datasets/{owner}': {'get': {}}}}):
            client = Platform(key='ul_'+'0'*40)  # fixture, not an actual credential
        with patch.object(client, '_get', return_value={'datasets': []}) as get:
            client.get('/api/datasets/{owner}', owner='test-owner')
            get.assert_called_once_with('/api/datasets/test-owner')
            with self.assertRaisesRegex(ValueError, 'Invalid'):
                client.get('/api/datasets/{owner}', owner='../outside')
            with self.assertRaisesRegex(ValueError, 'absent'):
                client.get('/api/unsupported')

    def test_read_access_does_not_claim_write_or_import(self):
        client = Mock()
        client.get.side_effect = [{}, {}, {'datasets': []}]
        report = access_report(client, 'test-owner')
        self.assertTrue(report['authenticated'])
        self.assertFalse(report['write_permission_verified'])
        self.assertFalse(report['job_launched'])
        self.assertEqual(client.get.call_count, 3)


if __name__ == '__main__':
    unittest.main()
