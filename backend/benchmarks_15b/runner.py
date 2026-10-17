"""NeedProof 15B local evaluation. No network, users, secrets, or cloud clients.

Important: hand-authored SYNTHETIC benchmarks validate method behavior and
instrumentation; they cannot prove external accuracy, calibrated probabilities,
or causal business lift. Refuse to convert unverified evidence to purchase approval.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from statistics import mean

from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review, _tokens
from app.algorithms.evsi import Offer, VerificationAction, plan_verifications, bayes_update
from app.basket_optimizer_14a2 import BasketPlan14A2, evaluate_basket_14a2, _eligible_checks
from app.retail_forecast_14b1 import ForecastInput14B1, _predict, evaluate_retail_forecast_14b1

FIXTURE_PATH = Path(__file__).with_name('fixtures.json')
METHOD = 'OFFLINE_SYNTHETIC_FIXED_CASES_HOLDOUT_15B'


def fixture_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def load_fixtures() -> dict:
    data = json.loads(fixture_bytes())
    if data['origin'] != 'HAND_AUTHORED_SYNTHETIC_ILLUSTRATIVE_NOT_EXTERNAL':
        raise ValueError('Benchmark provenance label missing')
    return data


def _avg(vals):
    return round(mean(vals), 6) if vals else None


def _metrics_rank(results: list[dict], field: str) -> dict:
    ranks = [row[field] for row in results]
    return {'cases': len(ranks), 'hit_at_1': round(sum(x == 1 for x in ranks) / len(ranks), 6),
            'recall_at_3': round(sum(x <= 3 for x in ranks) / len(ranks), 6),
            'mrr': round(mean(1 / x for x in ranks), 6)}


def retrieval_benchmark(data: dict) -> dict:
    rows = []
    citations_total = 0
    for case in data['retrieval']:
        sources = [dict(source_id=sid, title=title, excerpt=excerpt, captured_at='2026-06-01T00:00:00+00:00', facts=[])
                   for sid, title, excerpt in case['sources']]
        payload = RetrievalInput.model_validate({'query':case['query'], 'review':{
            'product_label':'Example product', 'device_model':'Demo device', 'device_supports_usb_pd':True,
            'required_power_w':65, 'required_voltage_v':20, 'sources':sources}})
        result = retrieve_and_review(payload)
        assert result['purchase_allowed'] is False and result['sources_verified'] is False
        by_id = {s['source_id']: s for s in sources}
        actual_ranked = []
        for passage in result['passages']:
            original = by_id[passage['source_id']]['excerpt']
            assert original[passage['start']:passage['end']] == passage['quote'], 'Broken citation offset'
            assert sha256(original.encode('utf-8')).hexdigest() == passage['source_sha256']
            citations_total += 1
            if passage['source_id'] not in actual_ranked:
                actual_ranked.append(passage['source_id'])
        # Passage-level ranks; a relevant document might appear at rank >3 if multiple
        # irrelevant passages from the same source precede it. Record exactly that.
        actual_rank = next((i+1 for i,p in enumerate(result['passages'])
                            if p['source_id']==case['positive']), 7)
        # Fixed simple baseline: unique query-token overlap per document, no BM25/char grams.
        qwords = set(_tokens(case['query']))
        naive = sorted(case['sources'], key=lambda s: (-len(qwords & set(_tokens(s[1]+' '+s[2]))), s[0]))
        baseline_rank = next(i+1 for i,s in enumerate(naive) if s[0]==case['positive'])
        rows.append({'case_id':case['id'], 'expected_source_id':case['positive'],
                     'model_rank':actual_rank, 'token_overlap_rank':baseline_rank,
                     'passages_inspected':len(result['passages'])})
    return {'evaluation':'LABELED_HAND_AUTHORED_SOURCE_RETRIEVAL',
            'candidate_method':'LOCAL_BM25_CHAR_TRIGRAM_NO_EMBEDDINGS',
            'baseline_method':'UNIQUE_QUERY_TOKEN_OVERLAP',
            'candidate':_metrics_rank(rows,'model_rank'),
            'baseline':_metrics_rank(rows,'token_overlap_rank'),
            'citations_offsets_and_hashes_checked':citations_total,
            'cases':rows,
            'limitations':['Each label is hand-authored, not independently annotated.',
                           'Retrieval queries are constructed from the same synthetic source vocabulary.',
                           'No external product-search benchmark, human usefulness scores, or statistical power.']}


def evsi_benchmark(data: dict) -> dict:
    rows=[]
    for case in data['evsi']:
        offers=[]; actions=[]
        for i,(price,prior,response,cost,delay) in enumerate(zip(
                case['prices_minor'],case['priors'],case['responses'],case['costs_minor'],case['delays_minutes'])):
            sku=f"{case['id']}_offer{i}"
            offers.append(Offer(sku, f'Synthetic merchant {i}', price, 0, False,False,False))
            actions.append(VerificationAction('CHECK_'+sku,sku,Decimal(prior),Decimal(response),cost,delay))
        outcome=plan_verifications(offers,actions,budget_minor=80000,deadline_minutes=10,
                                   fulfillment_value_minor=20000,delay_cost_minor_per_minute=60)
        eligible=[r for r in outcome['actions'] if r['skip_reason'] is None]
        cost_first=min(eligible,key=lambda r:(Decimal(r['verification_cost_inr']),r['action_id']),default=None)
        if outcome['recommended_action_id']:
            chosen=next(r for r in eligible if r['action_id']==outcome['recommended_action_id'])
            chosen_net=Decimal(chosen['net_evsi_inr'])
        else:
            chosen_net=Decimal(0)
        # Baseline also has option to stop; no negative benchmark utility.
        cost_net=max(Decimal(0),Decimal(cost_first['net_evsi_inr'])) if cost_first else Decimal(0)
        assert chosen_net >= cost_net, 'Ranked EVSI unexpectedly worse than cost-first under the SAME assumed objective'
        rows.append({'case_id':case['id'], 'recommended_action_id':outcome['recommended_action_id'],
                     'baseline_action_id':cost_first['action_id'] if cost_first else None,
                     'evsi_expected_net_inr':float(chosen_net),
                     'cost_first_expected_net_inr':float(cost_net),
                     'synthetic_assumed_gain_inr':float(chosen_net-cost_net),
                     'no_real_merchant_contact':True})
    return {'evaluation':'MODEL_EXPECTED_ONE_STEP_NET_EVSI', 'cases':rows,
            'mean_modeled_gain_inr':_avg([r['synthetic_assumed_gain_inr'] for r in rows]),
            'cases_with_positive_gain':sum(r['synthetic_assumed_gain_inr']>0 for r in rows),
            'limitations':['An optimization compared against its own objective is not independent outcome validation.',
                           'Priors, utilities, response rates, and perfect verification are synthetic assumptions.',
                           'Modeled expected value is not observed merchant response or realized customer benefit.']}


def basket_benchmark(data: dict) -> dict:
    rows=[]
    for case in data['baskets']:
        merchants=[{'merchant_id':'a','name':'Synthetic A','fulfillment_fee_minor':case['fee_a']},
                   {'merchant_id':'b','name':'Synthetic B','fulfillment_fee_minor':case['fee_b']}]
        items=[{'item_id':f'i{i}','name':f'Example item {i}', 'quantity':1} for i in (0,1)]
        offers=[]
        for mid,prices,eta in [('a',case['prices_a'],8),('b',case['prices_b'],12)]:
            for i,price in enumerate(prices):
                offers.append({'sku':f'{mid}_{i}', 'item_id':f'i{i}', 'merchant_id':mid,
                               'product_name':f'Example item {i}', 'unit_price_minor':price,
                               'stock_on_hand':1, 'delivery_eta_minutes':eta,
                               'merchant_verified':True,'stock_verified':True,
                               'compatibility_verified':True,'delivery_verified':True,
                               'evidence_source':'SIMULATION_VERIFIED'})
        # Deliberately add the cheapest NON-VERIFIED offer: must never be selected.
        offers.append({'sku':'unverified_trap','item_id':'i0','merchant_id':'a',
                       'product_name':'Example item 0', 'unit_price_minor':100,
                       'stock_on_hand':5,'delivery_eta_minutes':1,
                       'merchant_verified':True,'stock_verified':True,
                       'compatibility_verified':True,'delivery_verified':True,
                       'evidence_source':'MERCHANT_REPORTED_UNVERIFIED'})
        payload=BasketPlan14A2.model_validate({
            'items':items,'merchants':merchants,'offers':offers,'budget_minor':case['budget'],
            'deadline_minutes':case['deadline'],'max_merchants':2,
            'hypothetical_scenario_acknowledged':True})
        out=evaluate_basket_14a2(payload)
        assert out['purchase_allowed'] is False and out['real_merchant_inventory_verified'] is False
        picked=out['synthetic_optimum']['selected_offers']
        assert all(o['sku']!='unverified_trap' for o in picked)
        optimum=out['synthetic_optimum']['totals']
        # Cost-first per line, ignoring merchant fees WHEN CHOOSING offers;
        # afterwards add all incurred merchant fees and check feasibility.
        quantity={i.item_id:i.quantity for i in payload.items}
        choices=[]
        for item in payload.items:
            eligible=[o for o in payload.offers if o.item_id==item.item_id
                      and not _eligible_checks(o,quantity[item.item_id],payload.deadline_minutes)]
            if not eligible:
                break
            choices.append(min(eligible,key=lambda o:(o.unit_price_minor,o.sku)))
        cost_first_total=None; cost_first_feasible=False
        if len(choices)==len(payload.items):
            used={o.merchant_id for o in choices}
            cost_first_total=sum(o.unit_price_minor*quantity[o.item_id] for o in choices) + sum(
                m.fulfillment_fee_minor for m in payload.merchants if m.merchant_id in used)
            cost_first_feasible=cost_first_total<=payload.budget_minor
        optimum_total=optimum['total_minor'] if optimum else None
        if optimum_total is not None and cost_first_feasible:
            assert optimum_total <= cost_first_total
        rows.append({'case_id':case['id'],'optimizer_status':out['scenario_status'],
                     'optimizer_total_minor':optimum_total,'per_item_cheapest_total_minor':cost_first_total,
                     'per_item_cheapest_feasible':cost_first_feasible,
                     'modeled_savings_minor':(cost_first_total-optimum_total)
                          if optimum_total is not None and cost_first_feasible else None,
                     'unverified_trap_excluded':all(o['sku']!='unverified_trap' for o in picked),
                     'purchase_allowed':False})
    comparable=[r['modeled_savings_minor'] for r in rows if r['modeled_savings_minor'] is not None]
    return {'evaluation':'SYNTHETIC_FEASIBLE_BASKET_TOTAL_IN_MINOR_UNITS',
            'cases':rows,'comparable_cases':len(comparable),'mean_cost_saving_minor':_avg(comparable),
            'limitations':['Both solver and baseline use artificial fixture prices/stock.',
                           'Unverified reports are not made eligible; this is not merchant inventory.',
                           'Constraint satisfaction is proven only for tiny illustrative cases.']}


def forecast_benchmark(data: dict) -> dict:
    rows=[]
    for kind in data['forecasts']:
        size=98; start=date(2026,1,1)
        values=[]
        for i in range(size):
            if kind=='weekly_pattern':
                value=[5,5,6,6,8,16,14][i%7]
            elif kind=='rising_sales':
                value=max(0,5+i//9)
            elif kind=='flat':
                value=10
            elif kind=='all_zero':
                value=0
            else:
                raise ValueError('Unknown synthetic series')
            values.append(value)
        cutoff=84; holdout=14; horizon=14
        train=[{'day':(start+timedelta(days=i)).isoformat(),'units_sold':v}
               for i,v in enumerate(values[:cutoff])]
        model_input=ForecastInput14B1.model_validate({'product_label':'Synthetic '+kind,
              'history':train,'horizon_days':horizon,'synthetic_demo':True})
        fit=evaluate_retail_forecast_14b1(model_input)
        assert fit['target']=='OBSERVED_UNIT_SALES_AS_DEMAND_PROXY' and fit['purchase_allowed'] is False
        assert fit['data_origin']=='CLIENT_LABELED_SYNTHETIC_DEMO'
        prediction=[p['expected_units'] for p in fit['predictions']]
        hold=values[cutoff:cutoff+holdout]
        mae=sum(abs(p-y) for p,y in zip(prediction,hold))/len(hold)
        baseline_pred=_predict('moving_average_7',values[:cutoff],horizon)
        baseline_mae=sum(abs(p-y) for p,y in zip(baseline_pred,hold))/len(hold)
        # Only selection data precedes independent last-14-day evaluation.
        assert fit['training_observations']==cutoff
        rows.append({'case_id':kind,'training_days':cutoff,'untouched_holdout_days':holdout,
                     'chosen_method':fit['selected_model'], 'selected_mae_units':round(mae,4),
                     'moving_avg_7_mae_units':round(baseline_mae,4),
                     'selected_minus_baseline_mae_units':round(mae-baseline_mae,4)})
    return {'evaluation':'STRICTLY_LATER_FIXED_SYNTHETIC_HOLDOUT', 'cases':rows,
            'mean_selected_mae_units':_avg([r['selected_mae_units'] for r in rows]),
            'mean_moving_avg_mae_units':_avg([r['moving_avg_7_mae_units'] for r in rows]),
            'limitations':['Weekly/flat/trend/zero sequences are engineered, not retailer datasets.',
                           'One fixed later holdout per series, not an independent field trial.',
                           'Accuracy on observed sales is not accuracy on censored latent demand.']}


def bayesian_benchmark(data: dict) -> dict:
    rng=Random(data['seed'])
    n=data['synthetic_bayesian_trials']
    y=[]; priors=[]; posterior=[]
    for _ in range(n):
        truth=1 if rng.random()<0.5 else 0
        signal=rng.random() < (0.8 if truth else 0.25)
        y.append(truth)
        priors.append(0.5)
        posterior.append(float(bayes_update(Decimal('0.5'),Decimal('0.8'),Decimal('0.75'),signal)))
    def brier(pred):
        return round(mean((p-t)**2 for p,t in zip(pred,y)),6)
    def ece(pred,bins=5):
        total=0.0
        for j in range(bins):
            idx=[i for i,p in enumerate(pred) if (j/bins<=p<(j+1)/bins or (j==bins-1 and p==1))]
            if idx:
                total+=len(idx)/len(pred)*abs(mean(pred[i] for i in idx)-mean(y[i] for i in idx))
        return round(total,6)
    return {'evaluation':'SEEDED_SYNTHETIC_SIGNAL_GENERATOR', 'trials':n,
            'baseline_prior_brier':brier(priors),'posterior_brier':brier(posterior),
            'posterior_ece_5_bins':ece(posterior), 'generator_assumed_sensitivity':0.8,
            'generator_assumed_specificity':0.75,
            'limitations':['Signal generator exactly matches assumed Bayes likelihoods by construction.',
                           'Brier and calibration diagnostics do NOT calibrate merchant reliability.',
                           'Synthetic trials must not be presented as real labeled outcomes.']}


def run_all() -> dict:
    fixture=load_fixtures()
    anchored = (
        'app/product_retrieval_13c2.py', 'app/evidence_planner_14a1.py',
        'app/basket_optimizer_14a2.py', 'app/retail_forecast_14b1.py',
    )
    backend_root=Path(__file__).resolve().parents[1]
    code_sha256={rel:sha256((backend_root/rel).read_text(encoding='utf-8-sig').replace('\r\n','\n').encode('utf-8')).hexdigest() for rel in anchored}
    return {'schema_version':'needproof-benchmark-15b-v1', 'method':METHOD, 'code_sha256':code_sha256,
            'fixture_sha256':sha256(fixture_bytes()).hexdigest(),
            'fixture_origin':fixture['origin'], 'seed':fixture['seed'],
            'retrieval':retrieval_benchmark(fixture),
            'evsi':evsi_benchmark(fixture),
            'basket':basket_benchmark(fixture),
            'forecast':forecast_benchmark(fixture),
            'bayesian':bayesian_benchmark(fixture),
            'global_limitations':[
                'Offline illustrative algorithm evaluation only: small hand-authored/synthetic tasks.',
                'Not a blind or representative independent corpus; no external merchant data or ground-truth stock.',
                'No financial uplift, environmental benefit, discrimination/fairness, runtime scalability, or live reliability claim.',
                'Purchase approval is ALWAYS false; user documents and merchant statements remain unverified.',
                'No Gemini, Places, Firebase, Cloud Run, BigQuery, or Firestore calls are made.',
            ]}


def write_reports(destination: Path, result:dict) -> tuple[Path,Path]:
    destination.mkdir(parents=True,exist_ok=True)
    report_json=destination/'report.json'
    report_md=destination/'report.md'
    report_json.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    r=result['retrieval']; e=result['evsi']; b=result['basket']; f=result['forecast']; cal=result['bayesian']
    md=f'''# NeedProof AI — Chunk 15B Synthetic Benchmark Report

**Dataset:** hand-authored synthetic cases. **Not** independent retail-world proof.

- Fixture SHA-256: `{result['fixture_sha256']}`
- Core module SHA-256 hashes: see `report.json`
- Reproducibility seed: `{result['seed']}`
- Cloud API calls: **none**; production mutation: **none**

## Illustrative results

| Measure | Candidate | Comparator | Interpretation |
|---|---:|---:|---|
| Retrieval top-1 hit | {r['candidate']['hit_at_1']:.3f} | {r['baseline']['hit_at_1']:.3f} | {r['candidate']['cases']} hand-labeled searches |
| Retrieval MRR | {r['candidate']['mrr']:.3f} | {r['baseline']['mrr']:.3f} | token overlap comparator |
| EVSI modeled net gain | INR {e['mean_modeled_gain_inr']:.2f} | INR 0.00 | vs cheaper verification action under same assumed model |
| Basket feasible savings | {b['mean_cost_saving_minor']} minor units | 0 | {b['comparable_cases']} feasible comparisons only |
| Forecast later holdout MAE | {f['mean_selected_mae_units']} units | {f['mean_moving_avg_mae_units']} units | mean across {len(f['cases'])} synthetic series |
| Bayesian Brier | {cal['posterior_brier']} | {cal['baseline_prior_brier']} | synthetic signals with assumed likelihoods |

Citation passage offsets and source hashes checked: **{r['citations_offsets_and_hashes_checked']}**.

## Scientific limitations

'''
    md+='\n'.join(f'- {x}' for x in result['global_limitations'])+'\n'
    md+='\n## Interpretation\n\nThese measurements are **engineering smoke benchmarks**. Only a separate frozen external/human-annotated test corpus, representative cases, independent reliability labels, appropriate confidence intervals, and real-world operational measurements can substantiate generalized accuracy, true calibration, cost reductions or shortlist-readiness claims.\n'
    report_md.write_text(md,encoding='utf-8')
    return report_json,report_md
