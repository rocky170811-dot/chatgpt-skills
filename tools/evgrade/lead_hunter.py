"""EvGrade data quality layer. No crawler, scheduler or outbound messaging.

Consumes connector JSON {values: [...]} and emits local audit CSV/JSON.
Never treats a published contact or an old score as current verification.
"""
import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

EMPTY = {'', '—', '-', 'не найден публично'}

def present(value):
    return str(value or '').strip().lower() not in EMPTY

def domain(value):
    value = str(value or '').strip()
    if not value or ' ' in value:
        return ''
    host = urlsplit(value if '://' in value else 'https://' + value).hostname or ''
    return host.lower().removeprefix('www.').encode('idna').decode()

def score(evidence):
    """Evidence must be validated by caller; fit is independent of send approval."""
    weights = {'english': 10, 'sector': 15, 'smb_confirmed': 15,
               'phone_sales': 20, 'sales_team': 15, 'qa_or_growth': 15,
               'public_business_contact': 10}
    total = sum(w for key, w in weights.items() if evidence.get(key) is True)
    if evidence.get('competitor') or evidence.get('suppressed'):
        return 0
    return total

class Ledger:
    """Single-writer local checkpoint. Mark done only after Sheets readback.

    This does not lock out an unknown external writer; the hosting scheduler
    must provide that lock before enabling unattended updates.
    """
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS checkpoints '
                        '(run_key TEXT PRIMARY KEY, payload TEXT NOT NULL, verified INTEGER NOT NULL)')

    def stage(self, run_key, payload):
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self.db:
            old = self.db.execute('SELECT payload, verified FROM checkpoints WHERE run_key=?',
                                  (run_key,)).fetchone()
            if old:
                if old[0] != encoded:
                    raise ValueError('Run key already exists with a different payload')
                return not bool(old[1])
            self.db.execute('INSERT INTO checkpoints VALUES (?, ?, 0)', (run_key, encoded))
        return True

    def confirm(self, run_key, expected, actual):
        if expected != actual:
            raise ValueError('Readback mismatch; checkpoint remains pending')
        encoded = json.dumps(expected, ensure_ascii=False, sort_keys=True)
        with self.db:
            cursor = self.db.execute('UPDATE checkpoints SET verified=1 WHERE run_key=? AND payload=?',
                                     (run_key, encoded))
            if cursor.rowcount != 1:
                raise ValueError('Unknown run or payload mismatch')

def plan_upserts(existing, incoming):
    """Input is normalized dictionaries, not positional Sheet cells.

    Conflicting domain/id identity halts the batch; never overwrites manual CRM
    fields. Branch/subdomain and fuzzy-name matches require human identity review.
    """
    protected = {'status', 'owner', 'next_contact', 'comment', 'suppressed'}
    by_id, by_domain = {}, {}
    for item in existing:
        if item['id'] in by_id:
            raise ValueError('Duplicate existing ID')
        by_id[item['id']] = item
        key = domain(item.get('website'))
        if key:
            if key in by_domain:
                raise ValueError('Duplicate existing domain needs identity review')
            by_domain[key] = item
    output, seen = [], set()
    for item in incoming:
        key = domain(item.get('website'))
        identity = key or item['id']
        if identity in seen:
            raise ValueError('Duplicate incoming identity')
        seen.add(identity)
        old_id, old_domain = by_id.get(item['id']), by_domain.get(key)
        if old_id and old_domain and old_id['id'] != old_domain['id']:
            raise ValueError('ID/domain conflict')
        old = old_id or old_domain
        if old and old.get('suppressed'):
            continue
        merged = dict(old or {})
        merged.update({k: v for k, v in item.items() if k not in protected})
        if old:
            merged['id'] = old['id']
        output.append({'action': 'update' if old else 'insert', 'record': merged})
    return output

def draft(company, observation, greeting='Hello', case_claim=False):
    # Only insert observations backed by a recorded URL. No inferred pain/volume.
    case = (' A veterinary clinic network increased booking conversion by 37%.'
            if case_claim else '')
    return (f'{greeting},\n\nI noticed that {observation}\n\n'
            'I’m reaching out from EvGrade Tech. When a team handles customer calls, '
            'reviewing every conversation manually can be difficult. Our AI analyses '
            'calls and flags missed next steps, unclear price explanations and '
            'opportunities to follow up. Managers receive a daily team summary.' + case +
            f'\n\nWould you consider a pilot with one team at {company}? We can review '
            'a sample of your calls, show what the service finds and estimate the '
            'potential return. The introductory 40-minute call is free.\n\n'
            'When would be convenient?')

def audit(values, source_hyperlinks=None):
    if not values or values[0][:5] != ['№', 'Комментарии', 'Важная инф', 'Страна', 'Компания']:
        raise ValueError('Unexpected source schema; do not guess column mapping')
    records, names = [], {}
    for rownum, original in enumerate(values[1:], 2):
        if not any(present(x) for x in original):
            continue
        row = list(original) + [''] * max(0, 19-len(original))
        issues = []
        if not re.fullmatch(r'\d+', str(row[0] or '')):
            records.append({'row': rownum, 'company': '', 'result': 'SCHEMA_DRIFT',
                            'issues': 'Shifted columns; preserve original, review mapping',
                            'duplicate_of': ''})
            continue
        name = str(row[4] or '').strip()
        key = re.sub(r'\W+', '', name.casefold())
        duplicate = names.get(key, '') if key else ''
        if key:
            names.setdefault(key, rownum)
        if duplicate:
            issues.append('duplicate company name: manual identity check')
        if not domain(row[5]) and not domain(row[18]):
            issues.append('official website missing')
        if not present(row[14]) and not present(row[15]):
            issues.append('business contact missing')
        source = (source_hyperlinks or {}).get(str(rownum), str(row[11] or ''))
        if not source.startswith('http'):
            issues.append('source is display text; inspect hyperlink target')
        elif re.search(r'/(vacancies(?:/|$)|search/vacancy)', urlsplit(source).path):
            issues.append('generic job search URL; employer-specific evidence missing')
        # Source schema has no checked_at, per-contact provenance or signal date.
        issues.append('freshness and contact provenance not recorded')
        records.append({'row': rownum, 'company': name, 'result': 'REVERIFY',
                        'issues': '; '.join(issues), 'duplicate_of': duplicate})
    return records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    records = audit(data['values'], data.get('source_hyperlinks'))
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'audit.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = {'rows_audited': len(records), 'results': dict(Counter(x['result'] for x in records)),
               'duplicate_name_rows': sum(bool(x['duplicate_of']) for x in records),
               'live_reverified': 0, 'send_approved': 0,
               'note': 'Structural audit only; no claim of 100 live-verified leads.'}
    (args.output/'audit-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == '__main__':
    main()
