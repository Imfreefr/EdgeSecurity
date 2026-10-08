import unittest
from unittest.mock import Mock, patch
from inspect_remote_zip import RangeReader


def response(status, content_range, data=b''):
    result = Mock()
    result.status_code = status
    result.headers = {'Content-Range': content_range}
    result.raw.read.return_value = data
    context = Mock()
    context.__enter__ = Mock(return_value=result)
    context.__exit__ = Mock(return_value=False)
    return context


class RangeTests(unittest.TestCase):
    def test_full_download_response_refused_without_reading_body(self):
        result = response(200, '')
        with patch('inspect_remote_zip.requests.get', return_value=result):
            with self.assertRaisesRegex(ValueError, 'full download refused'):
                RangeReader('https://example.test/archive.zip')
        result.__enter__.return_value.raw.read.assert_not_called()

    def test_expected_bounded_range(self):
        with patch('inspect_remote_zip.requests.get', side_effect=[response(206, 'bytes 0-0/100'),
                                                                  response(206, 'bytes 95-99/100', b'12345')]) as get:
            reader = RangeReader('https://example.test/archive.zip')
            reader.seek(-5, 2)
            self.assertEqual(reader.read(), b'12345')
            self.assertEqual(reader.transferred, 5)
            self.assertEqual(get.call_args.kwargs['headers']['Range'], 'bytes=95-99')

    def test_wrong_range_and_transfer_budget_rejected(self):
        with patch('inspect_remote_zip.requests.get', side_effect=[response(206, 'bytes 0-0/100'),
                                                                  response(206, 'bytes 1-2/100', b'12')]):
            reader = RangeReader('https://example.test/archive.zip')
            with self.assertRaisesRegex(ValueError, 'Unexpected range'):
                reader.read(2)
            reader.transferred = 8*1024*1024
            with self.assertRaisesRegex(ValueError, 'budget exceeded'):
                reader.read(1)


if __name__ == '__main__':
    unittest.main()
