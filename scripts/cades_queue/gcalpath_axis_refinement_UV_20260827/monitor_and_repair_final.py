#!/usr/bin/python3.11
from __future__ import annotations

import csv
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

BATCH = Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827')
MANIFEST = BATCH / 'manifest.tsv'
LEDGER = BATCH / 'submission_ledger.tsv'
STATE_FILE = BATCH / 'repair_state.json'
REPORT = BATCH / 'latest_report.json'
LOCK = BATCH / '.monitor.lock'
FAILURE = {'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE', 'CANCELLED', 'REVOKED'}
ACTIVE = {'PENDING', 'RUNNING', 'CONFIGURING', 'COMPLETING', 'SUSPENDED'}
REPAIR_ACCOUNT = 'ccsd'
SEED_RE = re.compile(r'^export QBASIS_LANCZOS_SEED=(\d+)\s*$', re.M)
sys.path.insert(0, str(BATCH))
from validate_pair import validate_pair


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def normalize(value):
    return value.strip().split('+', 1)[0].split()[0] if value.strip() else ''


def valid(row):
    return validate_pair(Path(row['gp']), Path(row['gh']), float(row['U']), float(row['V']), float(row['tp']))['valid']


def load_state():
    if STATE_FILE.is_file():
        return json.loads(STATE_FILE.read_text())
    return {'version': 2, 'used_repair_seeds': [], 'targets': {}, 'events': []}


def save_json(path, value):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, path)


def queue():
    p = run(['squeue', '-u', os.environ['USER'], '-h', '-o', '%i|%j|%a|%T|%Z'])
    out = {}
    for line in p.stdout.splitlines():
        cols = [x.strip() for x in line.split('|')]
        if len(cols) == 5 and cols[4] == str(BATCH) and cols[1] in {'GAXR', 'GAXRR'}:
            out[cols[0]] = {'name': cols[1], 'account': cols[2], 'state': cols[3]}
    return out


def accounting(name):
    p = run(['sacct', '-S', '2026-08-27', '-n', '-X', '--name', name,
             '-o', 'JobIDRaw,Account,State%30,ExitCode', '-P'])
    out = {}
    for line in p.stdout.splitlines():
        cols = line.split('|')
        if len(cols) >= 4 and cols[0].strip().isdigit():
            out[cols[0].strip()] = {'account': cols[1].strip(), 'state': normalize(cols[2]), 'exit': cols[3].strip()}
    return out


def ledger():
    out = defaultdict(list)
    if not LEDGER.is_file():
        return out
    with LEDGER.open() as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            out[int(row['task_index'])].append(row)
    return out


def entry_seed(entry):
    try:
        match = SEED_RE.search(Path(entry['script']).read_text(errors='ignore'))
        return int(match.group(1)) if match else None
    except OSError:
        return None


def fresh_seed():
    while True:
        seed = random.SystemRandom().randint(1, 4294967295)
        if seed not in used:
            used.add(seed)
            return seed


def make_repair(row, account, round_number, copy_number, seed):
    idx = int(row['index'])
    work = BATCH / 'repairs' / f'task_{idx:04d}' / f'round_{round_number:04d}' / f'copy_{copy_number:02d}'
    work.mkdir(parents=True, exist_ok=True)
    template = BATCH / 'repair_templates' / f'repair_{idx:04d}_r{round_number:04d}_c{copy_number:02d}_A{account}.sh'
    text = (BATCH / 'job_template_body.sh').read_text()
    values = {
        '__JOB_NAME__': 'GAXRR', '__TASK_INDEX__': str(idx), '__WORK__': str(work),
        '__U__': row['U'], '__V__': row['V'], '__TP__': row['tp'],
        '__KX__': row['kx'], '__KY__': row['ky'], '__SEED__': str(seed),
        '__GP__': Path(row['gp']).name, '__GH__': Path(row['gh']).name,
    }
    for key, value in values.items():
        text = text.replace(key, value)
    template.write_text(text)
    template.chmod(0o700)
    subprocess.check_call(['bash', '-n', str(template)])
    return template, work


def migrate_target(target, idx, entries):
    if 'rounds' not in target:
        rounds = []
        repair_by_seed = {}
        for entry in entries:
            if entry.get('kind') == 'repair':
                seed = entry_seed(entry)
                if seed is not None:
                    repair_by_seed[seed] = entry
        for old in target.get('generations', []):
            seed = int(old['seed'])
            entry = repair_by_seed.get(seed)
            rounds.append({
                'round': int(old.get('generation', len(rounds) + 1)),
                'created_at': old.get('prepared_at'),
                'account': old.get('account', entry.get('account') if entry else 'ccsd'),
                'status': 'legacy_migrated',
                'copies': [{
                    'copy': 1, 'seed': seed, 'account': old.get('account', 'ccsd'),
                    'template': old.get('template'),
                    'workdir': str(BATCH / 'repairs' / f'task_{idx:04d}' / f"gen_{int(old.get('generation', 1)):04d}"),
                    'job_id': entry.get('job_id') if entry else None,
                    'status': 'submitted' if entry else 'prepared',
                }],
            })
        target['rounds'] = rounds
        target['legacy_generations'] = target.pop('generations', [])
    # Link submitted copies by their unique seed.
    copies_by_seed = {int(c['seed']): c for r in target.get('rounds', []) for c in r.get('copies', [])}
    for entry in entries:
        if entry.get('kind') != 'repair':
            continue
        seed = entry_seed(entry)
        copy = copies_by_seed.get(seed)
        if copy is not None:
            copy['job_id'] = entry['job_id']
            copy['submitted_script'] = entry['script']
            if copy.get('status') == 'prepared':
                copy['status'] = 'submitted'


def prepare_copy(idx, row, target, repair_round, account, copy_number):
    seed = fresh_seed()
    template, work = make_repair(row, account, int(repair_round['round']), copy_number, seed)
    record = {
        'copy': copy_number, 'seed': seed, 'account': account,
        'template': str(template), 'workdir': str(work), 'job_id': None,
        'status': 'prepared', 'prepared_at': time.strftime('%F %T'),
    }
    repair_round['copies'].append(record)
    item = {'task_index': idx, 'round': repair_round['round'], **record}
    prepared.append(item)
    return item


def start_round(idx, row, target, account):
    number = max([int(r.get('round', 0)) for r in target.get('rounds', [])] or [0]) + 1
    repair_round = {
        'round': number, 'created_at': time.strftime('%F %T'),
        'account': account, 'status': 'preparing_pair', 'copies': [],
    }
    target.setdefault('rounds', []).append(repair_round)
    prepare_copy(idx, row, target, repair_round, account, 1)
    prepare_copy(idx, row, target, repair_round, account, 2)
    repair_round['status'] = 'prepared_pair'
    target['status'] = 'repair_pair_prepared'
    return repair_round


def cancel_active_repairs(idx, entries, q):
    cancelled = []
    for entry in entries:
        jid = entry['job_id']
        if entry.get('kind') == 'repair' and jid in q:
            p = run(['scancel', jid])
            if p.returncode == 0:
                cancelled.append(jid)
    if cancelled:
        state['events'].append({'time': time.strftime('%F %T'), 'action': 'cancel_repair_siblings_after_valid_output',
                                'task_index': idx, 'job_ids': cancelled})
    return cancelled


lock_handle = LOCK.open('w')
try:
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    print('Another GAXR monitor is active; no action taken.')
    raise SystemExit(0)

rows = list(csv.DictReader(MANIFEST.open(), delimiter='\t'))
rows_by_index = {int(row['index']): row for row in rows}
state = load_state()
state['version'] = 2
state.setdefault('events', [])
state.setdefault('targets', {})
used = {int(row['seed']) for row in rows} | {int(x) for x in state.get('used_repair_seeds', [])}
q = queue()
sacct = {**accounting('GAXR'), **accounting('GAXRR')}
jobs = ledger()
prepared = []
cancelled = []

# Migrate/link all existing repair records before deciding whether a companion is missing.
for idx, target in state['targets'].items():
    migrate_target(target, int(idx), jobs.get(int(idx), []))

for idx, row in rows_by_index.items():
    entries = jobs.get(idx, [])
    if valid(row):
        cancelled.extend(cancel_active_repairs(idx, entries, q))
        target = state['targets'].get(str(idx))
        if target:
            target['status'] = 'resolved'
            target['resolved_at'] = time.strftime('%F %T')
        continue

    active_normal = [e for e in entries if e.get('kind') == 'normal' and e['job_id'] in q]
    if active_normal:
        continue

    target = state['targets'].setdefault(str(idx), {'rounds': [], 'row': row, 'status': 'needs_repair'})
    target['row'] = row
    migrate_target(target, idx, entries)
    active_repair_ids = {e['job_id'] for e in entries if e.get('kind') == 'repair' and e['job_id'] in q}

    active_round = None
    for repair_round in reversed(target.get('rounds', [])):
        copy_jobs = {c.get('job_id') for c in repair_round.get('copies', []) if c.get('job_id')}
        waiting = any(c.get('job_id') is None and Path(c.get('template', '')).is_file() for c in repair_round.get('copies', []))
        if copy_jobs.intersection(active_repair_ids) or waiting:
            active_round = repair_round
            break

    if active_round is not None:
        # Legacy single-copy repairs get exactly one distinct-seed companion.
        if len(active_round.get('copies', [])) < 2:
            account = REPAIR_ACCOUNT
            prepare_copy(idx, row, target, active_round, account, 2)
            active_round['status'] = 'prepared_pair'
        else:
            active_round['status'] = 'active_pair'
        target['status'] = 'repair_pair_active'
        continue

    repair_templates = list((BATCH / 'repair_templates').glob(f'repair_{idx:04d}_*.sh'))
    if repair_templates:
        continue
    ordinary_template = BATCH / 'templates' / f'job_gaxr_{idx:04d}.sh'
    if ordinary_template.exists() and not entries:
        continue
    if not entries:
        account = 'ccsd'
    else:
        last = entries[-1]
        terminal = sacct.get(last['job_id'])
        if terminal is None or terminal['state'] in ACTIVE:
            continue
        account = REPAIR_ACCOUNT
        target['last_failure_job_id'] = last['job_id']
        target['last_failure_state'] = terminal['state']
        target['last_failure_exit'] = terminal['exit']
    start_round(idx, row, target, account)

state['used_repair_seeds'] = sorted(used - {int(row['seed']) for row in rows})
if prepared:
    state['events'].append({'time': time.strftime('%F %T'), 'action': 'prepare_repair_copies', 'items': prepared})
save_json(STATE_FILE, state)

if not (BATCH / '.priority_pause').exists():
    env = os.environ.copy()
    env['GAXR_CONFIRM_SUBMIT'] = 'YES'
    subprocess.run(['bash', str(BATCH / 'submit_fill.sh'), 'all'], env=env, check=False)

# Refresh queue/ledger and attach newly submitted job IDs to state by seed.
q = queue()
jobs = ledger()
for idx, target in state['targets'].items():
    migrate_target(target, int(idx), jobs.get(int(idx), []))
for target in state['targets'].values():
    for repair_round in target.get('rounds', []):
        states = []
        for copy in repair_round.get('copies', []):
            jid = copy.get('job_id')
            if jid in q:
                copy['slurm_state'] = q[jid]['state']
                states.append(q[jid]['state'])
            elif jid in sacct:
                copy['slurm_state'] = sacct[jid]['state']
                states.append(sacct[jid]['state'])
        if any(s in ACTIVE for s in states):
            repair_round['status'] = 'active_pair'
        elif len(repair_round.get('copies', [])) == 2 and states:
            repair_round['status'] = 'terminal_pair'
save_json(STATE_FILE, state)

case = defaultdict(lambda: {'total': 0, 'complete': 0, 'running': 0, 'pending': 0, 'waiting': 0, 'repair_waiting': 0})
for idx, row in rows_by_index.items():
    key = (row['U'], row['V'], row['tp'], row['set_name'])
    stat = case[key]
    stat['total'] += 1
    if valid(row):
        stat['complete'] += 1
        continue
    entries = jobs.get(idx, [])
    active_entries = [entry for entry in entries if entry['job_id'] in q]
    if active_entries:
        states = [q[entry['job_id']]['state'] for entry in active_entries]
        if any(value == 'RUNNING' for value in states):
            stat['running'] += 1
        else:
            stat['pending'] += 1
    elif (BATCH / 'templates' / f'job_gaxr_{idx:04d}.sh').exists():
        stat['waiting'] += 1
    elif list((BATCH / 'repair_templates').glob(f'repair_{idx:04d}_*.sh')):
        stat['repair_waiting'] += 1

cases = []
for (U, V, tp, set_name), stat in sorted(case.items(), key=lambda item: item[0][3]):
    cases.append({'U': U, 'V': V, 'tp': tp, 'set_name': set_name, **stat})
active_repair_copies = []
for idx, entries in jobs.items():
    for entry in entries:
        if entry.get('kind') == 'repair' and entry['job_id'] in q:
            active_repair_copies.append({'task_index': idx, 'job_id': entry['job_id'], 'account': entry['account'],
                                          'state': q[entry['job_id']]['state'], 'seed': entry_seed(entry)})
report = {
    'time': time.strftime('%F %T'), 'total': len(rows),
    'complete': sum(item['complete'] for item in cases),
    'cases': cases, 'repairs_prepared': prepared, 'repairs_cancelled': cancelled,
    'active_repair_copies': active_repair_copies,
    'repair_policy': 'exactly_two_concurrent_distinct_seeds_per_failed_target',
    'queue': {
        account: {
            state_name: sum(1 for item in q.values() if item['account'] == account and item['state'] == state_name)
            for state_name in ('RUNNING', 'PENDING')
        }
        for account in ('ccsd', 'cnms')
    },
}
save_json(REPORT, report)
print(f"GAXR progress at {report['time']}")
print(f"COMPLETE {report['complete']}/{report['total']} ({100.0*report['complete']/report['total']:.2f}%)")
for item in cases:
    print('U={U} V={V} tp={tp}: {complete}/{total} | R={running} PD={pending} waiting={waiting} repair_waiting={repair_waiting}'.format(**item))
print('QUEUE ccsd R={RUNNING} PD={PENDING}'.format(**report['queue']['ccsd']))
print('QUEUE cnms R={RUNNING} PD={PENDING}'.format(**report['queue']['cnms']))
print(f'REPAIR_COPIES_PREPARED {len(prepared)}')
print(f'REPAIR_SIBLINGS_CANCELLED {len(cancelled)}')
print(f'ACTIVE_REPAIR_COPIES {len(active_repair_copies)}')
if report['complete'] == report['total'] and not q and not prepared:
    print('ALL_COMPLETE')
