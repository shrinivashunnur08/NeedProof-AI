#!/usr/bin/env python3
"""Reproduce the 17F fictional comparison report; only local files, no network."""
from __future__ import annotations
import argparse
import csv
import html
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.benchmark_17f import load_cases, run_suite, POLICIES  # noqa:E402


def render_md(r):
    lines=['# NeedProof AI — Chunk 17F Synthetic Benchmark', '',
           '**Synthetic research fixture — not an independent retail pilot or validated impact result.**', '',
           f"Cases: **{r['dataset_size']}** · Dataset SHA-256: `{r['dataset_sha256']}` · Semantic results SHA-256: `{r['semantic_results_sha256']}`", '',
           '| Comparator | Correct states /40 | Correct next checks /40 | Unsafe provisional picks | Missed provisional picks | Unauthorized purchase | Median local ms |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for p,m in r['policies'].items():
        lines.append(f"| {p} | {m['correct_state']}/{m['case_count']} | {m['correct_first_check']}/{m['case_count']} | {m['false_provisional_offer']} | {m['missed_provisional_offer']} | {m['unauthorized_purchase']} | {m['median_local_microseconds']/1000:.3f} |")
    lines.extend(['','## Failure cases — do not hide mismatches',''])
    for p,rows in r['per_case'].items():
        mismatches=[x for x in rows if not x['correct_state'] or not x['correct_first_check'] or x['false_provisional_offer']]
        lines.extend([f'### {p}', '',f'{len(mismatches)} mismatched cases.', ''])
        for x in mismatches:
            lines.append(f"- `{x['case_id']}`: expected {x['expected_state']} / {x['expected_first_check']}; got {x['workflow_state']} / {x['first_verification_action']}; false provisional={x['false_provisional_offer']}")
        lines.append('')
    lines.extend(['## Case families',''])
    for family,n in r['family_counts'].items():lines.append(f'- {family}: {n}')
    lines.extend(['','## Methodological limitations',''])
    for l in r['limitations']: lines.append('- '+l)
    lines.extend(['','## Scope of claims','',
                  'No claims of real-world cost savings, avoided customer trips, conversion lift, merchant accuracy, independent ground truth, or relative superiority to a live LLM-only baseline.',''])
    return '\n'.join(lines)


def render_html(r):
    # Static, self-contained HTML; no external JS or CSS or network dependencies.
    esc=html.escape
    bars=[]
    for name,v in r['policies'].items():
        fraction=v['state_accuracy_fraction']
        bars.append(f'<div class="policy"><div class="headline"><strong>{esc(name)}</strong><span>{v["correct_state"]}/{v["case_count"]} correct states</span></div><div class="bar"><div class="fill" style="width:{fraction*100:.1f}%"></div></div><p>{v["correct_first_check"]} correct verification priorities · {v["false_provisional_offer"]} false provisional picks · {v["missed_provisional_offer"]} missed provisional offers</p></div>')
    rows=[]
    for name, entries in r['per_case'].items():
        for x in entries:
            ok = x['correct_state'] and x['correct_first_check'] and not x['false_provisional_offer']
            rows.append('<tr>'+''.join(f'<td>{esc(str(v))}</td>' for v in [name,x['case_id'],x['expected_state'],x['workflow_state'],x['expected_first_check'],x['first_verification_action'],'PASS' if ok else 'MISMATCH'])+'</tr>')
    caveats=''.join('<li>'+esc(l)+'</li>' for l in r['limitations'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NeedProof AI — 17F Synthetic Benchmark</title>
<style>body{font:15px/1.6 system-ui,Arial;background:#0b1324;color:#eef5ff;max-width:1100px;margin:0 auto;padding:32px}h1{font-size:2rem}a{color:#62dcea}.sub{color:#adbfda} .warning{padding:14px 17px;border:1px solid #dcb355;border-radius:10px;color:#f9d980;margin:18px 0} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.policy{background:#111e34;border:1px solid #29415c;border-radius:12px;padding:18px}.headline{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}.bar{height:13px;background:#2a364f;border-radius:12px;margin-top:14px;overflow:hidden}.fill{background:#36c9d9;height:100%}.policy p{font-size:13px;color:#aebed5}table{border-collapse:collapse;min-width:850px}th,td{text-align:left;padding:9px;border-bottom:1px solid #304057}th{position:sticky;top:0;background:#0e1b2d}.scroll{overflow:auto;max-height:520px;border:1px solid #304057;border-radius:10px}small{color:#adbfda}ul{max-width:880px}.tag{font-size:12px;color:#7cd6eb}</style>
<h1>NeedProof AI · 17F simulated benchmark</h1><p class="sub">40 hand-curated synthetic scenarios · source-visible comparators · fully offline execution</p><div class="warning"><strong>NOT FIELD VALIDATION.</strong> Dataset labels were authored by the builders. These results do not establish saved trips, real stock reliability, real customer impact or an advantage over a live LLM-only baseline.</div>
<h2>Correct decision states across identical inputs</h2><div class="grid">'''+''.join(bars)+'''</div>
<h2>Full case-by-case comparison (including failures)</h2><div class="scroll"><table><thead><tr><th>Policy</th><th>Case</th><th>Expected state</th><th>Observed state</th><th>Expected next check</th><th>Observed next check</th><th>Result</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<h2>Limitations and interpretation</h2><ul>'''+caveats+'''</ul><p><small>Data fingerprint: '''+esc(r['dataset_sha256'])+''' · Semantic output fingerprint: '''+esc(r['semantic_results_sha256'])+'''</small></p></html>'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',default=str(ROOT/'qa_reports'/'17f'))
    p.add_argument('--repeat',type=int,default=3)
    args=p.parse_args()
    dataset=load_cases(ROOT/'backend'/'fixtures'/'benchmark17f_cases.json')
    report=run_suite(dataset,repetitions=args.repeat)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/'benchmark_results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (out/'benchmark_report.md').write_text(render_md(report),encoding='utf-8')
    (out/'benchmark_dashboard.html').write_text(render_html(report),encoding='utf-8')
    with (out/'case_comparison.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['policy','case_id','family','expected_state','workflow_state','correct_state','expected_first_check','first_verification_action','correct_first_check','false_provisional_offer','missed_provisional_offer','unauthorized_purchase']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for policy, rows in report['per_case'].items():
            for r in rows:writer.writerow({'policy':policy,**{k:r[k] for k in fields if k!='policy'}})
    print('PASS: 40 fictional cases x 4 comparators = 160 first-pass evaluations (plus local timing repetitions).')
    for policy,m in report['policies'].items():
        print(f"{policy}: decision {m['correct_state']}/40; next proof {m['correct_first_check']}/40; unsafe provisional {m['false_provisional_offer']}; median local ms {m['median_local_microseconds']/1000:.3f}")
    print('SEMANTIC_DIGEST:',report['semantic_results_sha256'])
    print('REPORTS:',out)
    print('LIMITATION: Authored synthetic labels. NO real shopper trips, costs, or live Gemini/LLM baseline measured.')

if __name__=='__main__':main()
