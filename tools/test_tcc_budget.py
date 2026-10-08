import unittest
from check_tcc_budget import preflight


class BudgetTests(unittest.TestCase):
    def test_only_preflight_never_launches(self):
        result = preflight({'runs': []}, '1.50', True, True)
        self.assertTrue(result['preflight_pass'])
        self.assertFalse(result['job_launched'])

    def test_missing_dataset_or_monitoring_blocks(self):
        self.assertFalse(preflight({'runs': []}, 1, False, True)['preflight_pass'])
        self.assertFalse(preflight({'runs': []}, 1, True, False)['preflight_pass'])

    def test_failed_cancelled_jobs_count_and_reserve_preserved(self):
        ledger = {'runs': [
            {'status': 'failed', 'actual_usd': '8', 'billing_settled': True},
            {'status': 'cancelled', 'actual_usd': '9', 'billing_settled': True}]}
        self.assertFalse(preflight(ledger, '1.01', True, True)['preflight_pass'])
        self.assertTrue(preflight(ledger, '1.00', True, True)['preflight_pass'])

    def test_unsettled_and_invalid_amounts_rejected(self):
        with self.assertRaises(ValueError):
            preflight({'runs': [{'status': 'running'}]}, 1, True, True)
        for amount in ('NaN', '-1', 'Infinity', 0):
            with self.assertRaises(ValueError):
                preflight({'runs': []}, amount, True, True)


if __name__ == '__main__':
    unittest.main()
