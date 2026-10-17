"""Offline benchmark runner; writes only user-visible local reports."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from benchmarks_15b.runner import run_all, write_reports


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,default=ROOT/'benchmark_reports'/'15b')
    parser.add_argument('--repeat-verify',action='store_true',default=False)
    args=parser.parse_args()
    result=run_all()
    if args.repeat_verify and result!=run_all():
        raise SystemExit('STOP: Non-reproducible benchmark outputs.')
    if not args.output_dir.is_relative_to(ROOT):
        raise SystemExit('STOP: Reports must remain inside repository working directory.')
    json_path,md_path=write_reports(args.output_dir,result)
    print('PASS: NeedProof 15B offline synthetic benchmark generated.')
    print('Data: hand-authored synthetic; no live usage or real-world accuracy claims.')
    print('Fixture sha256:',result['fixture_sha256'])
    print('Retrieval top1:',result['retrieval']['candidate']['hit_at_1'])
    print('Modeled EVSI gain (INR):',result['evsi']['mean_modeled_gain_inr'])
    print('Basket mean modeled saving (minor units):',result['basket']['mean_cost_saving_minor'])
    print('Forecast selected held-out MAE:',result['forecast']['mean_selected_mae_units'])
    print('Bayesian synthetic posterior Brier:',result['bayesian']['posterior_brier'])
    print('Output:',json_path)
    print('Output:',md_path)
    print('NO Cloud Run/Firebase/Gemini/Firestore/Places calls or deployments.')

if __name__=='__main__':
    main()
