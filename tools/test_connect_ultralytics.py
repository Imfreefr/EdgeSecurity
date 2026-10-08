import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from connect_ultralytics import check_and_save


class AccessDialogTests(unittest.TestCase):
    def test_only_sanitized_report_saved(self):
        client = Mock()
        fixture = 'ul_'+'0'*40
        safe_report = {'authenticated': True, 'job_launched': False}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'report.json'
            with patch('connect_ultralytics.Platform', return_value=client) as factory, \
                    patch('connect_ultralytics.access_report', return_value=safe_report):
                check_and_save(fixture, target)
            factory.assert_called_once_with(key=fixture)
            self.assertEqual(json.loads(target.read_text()), safe_report)
            self.assertNotIn(fixture, target.read_text())
            self.assertEqual(client.key, '')

    def test_failure_clears_client_key_without_success_file(self):
        client = Mock()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'report.json'
            with patch('connect_ultralytics.Platform', return_value=client), \
                    patch('connect_ultralytics.access_report', side_effect=ValueError('HTTP 401')):
                with self.assertRaises(ValueError):
                    check_and_save('ul_'+'0'*40, target)
            self.assertFalse(target.exists())
            self.assertEqual(client.key, '')


if __name__ == '__main__':
    unittest.main()
