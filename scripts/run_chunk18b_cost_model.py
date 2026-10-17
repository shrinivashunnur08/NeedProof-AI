#!/usr/bin/env python3
"""Pure illustrative cost arithmetic: NOT cloud billing, vendor pricing, or measured savings."""
from __future__ import annotations
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTIONS = ROOT / 'validation' / '18b' / 'hypothetical_cost_inputs.json'
OUT = ROOT / 'qa_reports' / '18b' / 'hypothetical_economics.json'


def compute(data):
    if data.get('provenance') != 'HYPOTHETICAL_UNVERIFIED_INPUTS':
        raise ValueError('Hypothetical-only provenance required')
    raw = data['assumptions']
    try:
        n = int(raw['journeys'])
        calls = Decimal(str(raw['model_calls_per_journey']))
        model_price = Decimal(str(raw['illustrative_usd_per_model_call']))
        backend_cost = Decimal(str(raw['illustrative_usd_per_backend_journey']))
        external_cost = Decimal(str(raw['illustrative_usd_per_optional_merchant_check']))
        merchant_fraction = Decimal(str(raw['fraction_requiring_merchant_check']))
    except (InvalidOperation, ValueError, KeyError) as exc:
        raise ValueError('Invalid arithmetic assumptions') from exc
    if n <= 0 or n > 1_000_000 or not all(Decimal('0') <= v <= Decimal('1000') for v in (calls, model_price, backend_cost, external_cost)) or not (0 <= merchant_fraction <= 1):
        raise ValueError('Out-of-range illustrative cost assumptions')
    total = (Decimal(n) * (calls * model_price + backend_cost + merchant_fraction * external_cost))
    return {
        'source': 'USER_EDITABLE_ILLUSTRATIVE_ASSUMPTIONS_NOT_VENDOR_PRICES',
        'journeys': n,
        'example_usd_per_journey': str((total / Decimal(n)).quantize(Decimal('0.0001'))),
        'example_total_usd': str(total.quantize(Decimal('0.01'))),
        'actual_billed_usd': None,
        'observed_shopper_value_usd': None,
        'observed_roi': None,
        'assumptions': raw,
        'limitations': 'No price verification, no actual API requests or bills, no measured customer outcomes or ROI.'
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, default=ASSUMPTIONS)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    try:
        result = compute(json.loads(args.inputs.read_text(encoding='utf8')))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
        print('HYPOTHETICAL ONLY —', result['journeys'], 'journeys, modeled total USD', result['example_total_usd'])
        print('ACTUAL CLOUD SPEND: NOT MEASURED. ROI: NOT MEASURED.')
        print('REPORT:', args.out.resolve())
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print('ERROR:', exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
