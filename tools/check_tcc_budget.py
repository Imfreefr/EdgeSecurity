"""Read-only paid-run preflight; never launches jobs or consumes credentials."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Invalid USD amount') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('Invalid USD amount')
    return amount


def preflight(ledger, estimated_usd, final_dataset_verified, monitoring_available):
    limit = Decimal('24.00')
    working_limit = Decimal('18.00')
    spent = Decimal('0')
    for run in ledger['runs']:
        if run.get('status') not in {'completed', 'cancelled', 'failed'} or run.get('billing_settled') is not True:
            raise ValueError('Running/unsettled jobs prevent a new run')
        spent += money(run['actual_usd'])
    estimate = money(estimated_usd)
    if estimate == 0:
        raise ValueError('Need actual platform estimate, not a zero placeholder')
    reasons = []
    if not final_dataset_verified:
        reasons.append('Final dataset/import not verified')
    if not monitoring_available:
        reasons.append('Cannot monitor/cancel paid run and bound billing exposure')
    if spent+estimate > working_limit:
        reasons.append('Would consume USD 6 safety reserve or exceed budget')
    if spent > limit:
        reasons.append('Total budget already exceeded; do not launch')
    return {'preflight_pass': not reasons, 'actual_spent_usd': str(spent),
            'estimate_usd': str(estimate), 'hard_total_limit_usd': str(limit),
            'working_limit_usd': str(working_limit), 'blockers': reasons,
            'job_launched': False,
            'notice': 'Estimate is not a charge cap. Recheck provider billing and monitoring before launching.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--estimate-usd', required=True)
    parser.add_argument('--final-dataset-verified', action='store_true')
    parser.add_argument('--monitoring-available', action='store_true')
    args = parser.parse_args()
    report = preflight(json.loads(Path(args.ledger).read_text(encoding='utf-8')),
                       args.estimate_usd, args.final_dataset_verified, args.monitoring_available)
    print(json.dumps(report, indent=2))
    if not report['preflight_pass']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
