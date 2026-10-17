"""18A optional consent-based local observations. Not an invented survey result.

No names, emails, phone numbers, free text or merchant identifiers recorded.
Output is private to this machine in qa_reports (not committed).
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'qa_reports' / '18a' / 'participants_local_only.csv'
FIELDS = ['recorded_utc', 'study_group', 'participant_code', 'task_code',
          'task_completed', 'decision_understanding_1_to_5', 'task_minutes',
          'consent_confirmed', 'real_observation']


def ask_one(prompt: str, allowed: set[str]) -> str:
    answer = input(prompt).strip().lower()
    if answer not in allowed:
        raise SystemExit(f'No record saved: response must be one of {sorted(allowed)}')
    return answer


def main() -> None:
    print('LOCAL STUDY ONLY. Please read validation/18a/RESEARCH_PROTOCOL.md first.')
    print('Participation is voluntary. Do not enter names, emails, phone numbers, merchant identities, or private shopping data.')
    consent = ask_one('Did participant give informed consent to anonymous local metrics? [yes/no]: ', {'yes', 'no'})
    if consent != 'yes':
        print('No consent. No data stored.')
        return
    group = ask_one('Role [shopper/merchant]: ', {'shopper', 'merchant'})
    code = input('Anonymous code (P1, P2, M1 etc; letters/numbers only): ').strip().upper()
    if not (2 <= len(code) <= 12 and code.isalnum()):
        raise SystemExit('No data stored: invalid anonymous code.')
    task = ask_one('Task [T1/T2/T3]: ', {'t1', 't2', 't3'})
    completed = ask_one('Task completed [yes/no]: ', {'yes', 'no'})
    score = ask_one('Understanding [1/2/3/4/5]: ', set('12345'))
    try:
        minutes = float(input('Observed minutes (0.1 to 120): ').strip())
    except ValueError as exc:
        raise SystemExit('Invalid duration; no data saved.') from exc
    if not 0.1 <= minutes <= 120:
        raise SystemExit('Invalid duration; no data saved.')
    row = [datetime.now(timezone.utc).isoformat(), group, code, task.upper(),
           completed, score, f'{minutes:.2f}', 'yes', 'yes']
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUTPUT.exists()
    with OUTPUT.open('a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(FIELDS)
        writer.writerow(row)
    print(f'Saved one consented observational row locally: {OUTPUT}')
    print('Never commit this file or claim these observations are representative.')


if __name__ == '__main__':
    main()
