"""Tests only the 18C release gate assertions; real verification is run via CMD."""
from __future__ import annotations
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import audit_chunk18c_release as gate


def a18():
    return {'provenance': 'AUTHOR_CREATED_FICTIONAL_18A', 'total_cases': 47,
            'passed': 47, 'failed': 0, 'real_participants': 0,
            'real_merchants': 0, 'verified_inventory': 0,
            'actual_gemini_calls': 0, 'actual_cloud_calls': 0,
            'results': [{'pass': True} for _ in range(47)]}


def b18():
    return {'schema': 'NEEDPROOF_18B_OFFLINE_ENGINEERING_V1',
            'provenance': 'AUTHOR_CREATED_FICTIONAL_18A',
            'passed': True, 'failures': [], 'actual_participants': 0,
            'actual_merchants': 0, 'verified_stock_observations': 0,
            'live_gemini_calls': 0, 'cloud_calls': 0,
            'schema_rejected_cases': list(range(10)),
            'input_signal_counterfactuals': list(range(5)),
            'policies': {key: {'tested':37,'correct':a,'false_provisional':b} for key, (a,b) in {
                'NEEDPROOF_17E':(37,0), 'PRICE_ONLY':(25,12),
                'STOCK_AND_BUDGET':(34,3), 'STRUCTURED_EVIDENCE_RULES':(37,0)}.items()}}


def cost():
    return {'source':'USER_EDITABLE_ILLUSTRATIVE_ASSUMPTIONS_NOT_VENDOR_PRICES',
            'actual_billed_usd':None,'observed_shopper_value_usd':None,'observed_roi':None}


def claims():
    return {'schema': 'NEEDPROOF_18C_RELEASE_CLAIMS_V1',
            'evidence_class':'OFFLINE_AUTHOR_CREATED_FICTIONAL',
            'purchase_authorization_enabled': False,
            'external_validation_claims': {
                'live_gemini_verified':False, 'secure_hosted_e2e_verified':False,
                'real_merchant_inventory_verified':False,
                'independent_user_pilot_completed':False,
                'actual_cost_and_roi_measured':False}}


def test_correct_fictional_data_passes():
    assert gate.validate_18a(a18()) == []


def test_claims_about_real_shoppers_are_rejected():
    r=a18();r['real_participants']=6
    assert gate.validate_18a(r)


def test_missing_individual_case_fails():
    r=a18();r['results'].pop()
    assert gate.validate_18a(r)


def test_structured_rules_tie_preserved():
    assert gate.validate_18b(b18()) == []


def test_fake_advantage_rejected():
    r=b18();r['policies']['STRUCTURED_EVIDENCE_RULES']['correct']=29
    assert gate.validate_18b(r)


def test_unsafe_decision_regression_rejected():
    r=b18();r['policies']['NEEDPROOF_17E']['false_provisional']=1
    assert gate.validate_18b(r)


def test_missing_signal_counterfactual_rejected():
    r=b18();r['input_signal_counterfactuals']=[]
    assert gate.validate_18b(r)


def test_hypothetical_cost_accepted():
    assert gate.validate_cost(cost()) == []


def test_fabricated_roi_fails():
    r=cost();r['observed_roi']='34%'
    assert gate.validate_cost(r)


def test_live_claims_cannot_pass_offline_audit():
    assert gate.validate_claims(claims()) == []
    r=copy.deepcopy(claims());r['external_validation_claims']['live_gemini_verified']=True
    assert gate.validate_claims(r)


def test_purchase_authorization_must_be_false():
    r=claims();r['purchase_authorization_enabled']=True
    assert gate.validate_claims(r)
