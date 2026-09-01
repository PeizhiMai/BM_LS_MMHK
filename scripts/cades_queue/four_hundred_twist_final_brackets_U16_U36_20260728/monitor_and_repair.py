#!/usr/bin/env python3
from __future__ import print_function

import csv
import fcntl
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time

BASE = Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs')
BATCH = BASE / 'transition_search' / 'four_hundred_twist_final_brackets_U16_U36_20260728'
MANIFEST = BATCH / 'manifest.tsv'
SUBMIT_LOG = BATCH / 'logs' / 'submit.log'
REPAIR = BATCH / 'auto_repair'
STATE_FILE = REPAIR / 'state.json'
LATEST_REPORT = REPAIR / 'latest_report.json'
LOCK_FILE = REPAIR / 'monitor.lock'
IGNORED_NORMAL_JOB_IDS = REPAIR / 'ignored_normal_job_ids.txt'
EXECUTABLE = BASE / 'Hubbard_sym_testobs_UV.x'
FAILURE_STATES = {
    'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED',
    'BOOT_FAIL', 'DEADLINE', 'CANCELLED', 'REVOKED',
}
ACTIVE_STATES = {'PENDING', 'RUNNING', 'CONFIGURING', 'COMPLETING', 'SUSPENDED'}
COMPLETE_RE = re.compile(r'(?m)^status\s+COMPLETE\s*$')
JOB_ID_RE = re.compile(r'Submitted batch job\s+(\d+)')
RESULT_RE = re.compile(r"^result='([^']+)'$", re.M)
COMMAND_RE = re.compile(
    r'\./Hubbard_sym_testobs_UV\.x\s+8\s+8\s+(\d+)\s+(\d+)\s+0\s+0\s+' 
    r'([^\s]+)\s+([^\s]+)\s+0(?:\s|$)'
)

REPAIR.mkdir(parents=True, exist_ok=True)
lock_handle = LOCK_FILE.open('w')
try:
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print('Another monitor/repair pass is already running; no action taken.')
    sys.exit(0)


def run(cmd, check=False):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    if check and p.returncode != 0:
        raise RuntimeError('{} failed ({}): {}'.format(' '.join(cmd), p.returncode, p.stderr))
    return p


def is_complete(path):
    p = Path(path)
    try:
        return p.is_file() and bool(COMPLETE_RE.search(p.read_text(errors='ignore')))
    except OSError:
        return False


def atomic_json(path, data):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    os.replace(str(tmp), str(path))


def load_state():
    if STATE_FILE.is_file():
        return json.loads(STATE_FILE.read_text())
    return {'version': 1, 'targets': {}, 'used_repair_seeds': [], 'events': []}


def save_state():
    atomic_json(STATE_FILE, state)


def normalize_state(raw):
    return raw.strip().split('+', 1)[0].split()[0] if raw.strip() else ''


def sacct_by_name(name):
    p = run(['sacct', '-S', '2026-07-26', '-n', '-X', '--name', name,
             '-o', 'JobIDRaw,Account,State%30,Elapsed,ExitCode', '-P'])
    records = {}
    for line in p.stdout.splitlines():
        cols = line.split('|')
        if len(cols) < 5:
            continue
        jid = cols[0].strip()
        if not jid or not jid.isdigit():
            continue
        records[jid] = {
            'account': cols[1].strip(),
            'state': normalize_state(cols[2]),
            'elapsed': cols[3].strip(),
            'exit_code': cols[4].strip(),
        }
    return records


def squeue_records():
    p = run(['squeue', '-u', os.environ['USER'], '-h', '-o', '%i|%j|%a|%T'])
    records = {}
    for line in p.stdout.splitlines():
        cols = [x.strip() for x in line.split('|')]
        if len(cols) != 4:
            continue
        records[cols[0]] = {'name': cols[1], 'account': cols[2], 'state': cols[3]}
    return records


def parse_normal_submissions():
    records = {}
    if not SUBMIT_LOG.is_file():
        return records
    for line in SUBMIT_LOG.read_text(errors='ignore').splitlines():
        parts = line.split('\t')
        if len(parts) < 4:
            continue
        m = JOB_ID_RE.search(parts[-1])
        if not m:
            continue
        jid = m.group(1)
        account = parts[1].strip()
        script = Path(parts[2].strip())
        if not script.is_file():
            continue
        text = script.read_text(errors='ignore')
        mr = RESULT_RE.search(text)
        mc = COMMAND_RE.search(text)
        if not (mr and mc):
            continue
        records[jid] = {
            'account': account,
            'script': str(script),
            'result': mr.group(1),
            'kx': int(mc.group(1)),
            'ky': int(mc.group(2)),
            'U': mc.group(3),
            'V': mc.group(4),
        }
    return records


def key_for(row):
    return 'U{}_V{}_f{}x{}'.format(row['U'], row['V'], row['kx'], row['ky'])


def slug(value):
    return str(value).replace('-', 'm').replace('+', 'p').replace('.', 'p')


def fresh_seed():
    while True:
        seed = random.SystemRandom().randint(1, 4294967295)
        if seed not in used_seeds:
            used_seeds.add(seed)
            state['used_repair_seeds'] = sorted(used_seeds)
            return seed


def submit_with_retry(script):
    last = None
    for _ in range(5):
        p = run(['sbatch', str(script)])
        last = p
        if p.returncode == 0:
            m = JOB_ID_RE.search(p.stdout)
            if m:
                return m.group(1)
        time.sleep(3)
    raise RuntimeError('Could not submit {}: {}'.format(script, (last.stderr if last else 'unknown')))


def make_repair_script(copy_dir, row, account, seed):
    result_name = Path(row['result']).name
    script = copy_dir / 'run_repair.sh'
    content = '''#!/bin/bash
#SBATCH -A {account}
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J OBS400R
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH -o {copy_dir}/OBS400R-%j.out
#SBATCH -e {copy_dir}/OBS400R-%j.err

set -uo pipefail
cd {copy_dir}
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED={seed}
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${{LD_LIBRARY_PATH:-}}
result='{copy_dir}/{result_name}'
rm -f "${{result}}"
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 {kx} {ky} 0 0 {U} {V} 0
rc=$?
set -e
if (( rc == 0 )) && [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{result}}"; then
  echo 'OBS400R_RESULT COMPLETE U={U} V={V} kx={kx} ky={ky} seed={seed}'
else
  echo 'OBS400R_RESULT FAILED rc='"${{rc}}"' U={U} V={V} kx={kx} ky={ky} seed={seed}' >&2
  (( rc == 0 )) && rc=90
fi
exit "${{rc}}"
'''.format(account=account, copy_dir=copy_dir, seed=seed,
           result_name=result_name, kx=row['kx'], ky=row['ky'],
           U=row['U'], V=row['V'])
    script.write_text(content)
    script.chmod(0o700)
    return script, copy_dir / result_name


def launch_pair(target_key, target):
    row = target['row']
    account = target.get('account') or 'ccsd'
    generation_number = len(target.setdefault('generations', [])) + 1
    generation_dir = REPAIR / 'cases' / target_key / 'gen{:03d}'.format(generation_number)
    generation_dir.mkdir(parents=True, exist_ok=True)
    generation = {
        'generation': generation_number,
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'submitting',
        'copies': [],
    }
    target['generations'].append(generation)
    target['status'] = 'repair_active'
    save_state()
    for copy_number in (1, 2):
        copy_dir = generation_dir / 'copy{}'.format(copy_number)
        copy_dir.mkdir(parents=True, exist_ok=True)
        binary = copy_dir / EXECUTABLE.name
        if not binary.exists():
            binary.symlink_to(EXECUTABLE)
        seed = fresh_seed()
        script, local_result = make_repair_script(copy_dir, row, account, seed)
        copy_record = {
            'copy': copy_number,
            'seed': seed,
            'script': str(script),
            'workdir': str(copy_dir),
            'local_result': str(local_result),
            'job_id': None,
            'status': 'prepared',
        }
        generation['copies'].append(copy_record)
        save_state()
        jid = submit_with_retry(script)
        copy_record['job_id'] = jid
        copy_record['status'] = 'submitted'
        save_state()
    generation['status'] = 'active'
    state['events'].append({
        'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'action': 'launch_pair',
        'target': target_key, 'generation': generation_number,
        'job_ids': [c['job_id'] for c in generation['copies']],
        'seeds': [c['seed'] for c in generation['copies']],
        'account': account,
    })
    save_state()
    return generation


def install_winner(target_key, target, copy_record, active_queue):
    source = Path(copy_record['local_result'])
    root = Path(target['row']['result'])
    tmp = root.parent / (root.name + '.repair.{}.tmp'.format(copy_record.get('job_id') or 'unknown'))
    shutil.copy2(str(source), str(tmp))
    if not is_complete(tmp):
        try: tmp.unlink()
        except OSError: pass
        raise RuntimeError('Candidate repair result is not COMPLETE: {}'.format(source))
    os.replace(str(tmp), str(root))
    if not is_complete(root):
        raise RuntimeError('Atomic repair install failed validation: {}'.format(root))
    cancelled = []
    for generation in target.get('generations', []):
        for sibling in generation.get('copies', []):
            jid = sibling.get('job_id')
            if jid and jid != copy_record.get('job_id') and jid in active_queue:
                run(['scancel', jid])
                cancelled.append(jid)
                sibling['status'] = 'cancelled_after_sibling_success'
    copy_record['status'] = 'winner_installed'
    target['status'] = 'resolved'
    target['winner_job_id'] = copy_record.get('job_id')
    target['resolved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    state['events'].append({
        'time': target['resolved_at'], 'action': 'install_winner',
        'target': target_key, 'winner_job_id': copy_record.get('job_id'),
        'cancelled_siblings': cancelled,
    })
    save_state()
    return cancelled


with MANIFEST.open() as f:
    rows = list(csv.DictReader(f, delimiter='\t'))
row_by_result = {r['result']: r for r in rows}
state = load_state()
used_seeds = {int(r['seed']) for r in rows}
used_seeds.update(int(x) for x in state.get('used_repair_seeds', []))
normal_jobs = parse_normal_submissions()
normal_sacct = sacct_by_name('OBS400')
repair_sacct = sacct_by_name('OBS400R')
active_queue = squeue_records()
ignored_normal_job_ids = set()
if IGNORED_NORMAL_JOB_IDS.is_file():
    ignored_normal_job_ids = {
        line.strip() for line in IGNORED_NORMAL_JOB_IDS.read_text().splitlines()
        if line.strip()
    }
active_normal_results = {
    job['result'] for jid, job in normal_jobs.items()
    if jid in active_queue
    and active_queue[jid]['name'] == 'OBS400'
    and active_queue[jid]['state'] in ACTIVE_STATES
}

new_failed_targets = []
for jid, job in normal_jobs.items():
    if jid in ignored_normal_job_ids:
        continue
    terminal = normal_sacct.get(jid)
    if not terminal:
        continue
    st = terminal['state']
    failed = st in FAILURE_STATES or (st == 'COMPLETED' and not is_complete(job['result']))
    if not failed or is_complete(job['result']):
        continue
    if job['result'] in active_normal_results:
        continue
    row = row_by_result.get(job['result'])
    if not row:
        continue
    key = key_for(row)
    target = state['targets'].setdefault(key, {
        'row': row, 'account': job['account'], 'original_jobs': [],
        'generations': [], 'status': 'needs_repair',
    })
    if jid not in target['original_jobs']:
        target['original_jobs'].append(jid)
        target['last_original_failure_state'] = st
        new_failed_targets.append(key)

repairs_launched = []
winners_installed = []
siblings_cancelled = []
for key, target in sorted(state['targets'].items()):
    root = target['row']['result']
    if is_complete(root):
        if target.get('status') != 'resolved':
            target['status'] = 'resolved'
            target['resolved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        continue

    winner = None
    for generation in target.get('generations', []):
        for copy_record in generation.get('copies', []):
            if is_complete(copy_record.get('local_result', '')):
                winner = copy_record
                break
        if winner:
            break
    if winner:
        cancelled = install_winner(key, target, winner, active_queue)
        winners_installed.append(key)
        siblings_cancelled.extend(cancelled)
        continue

    active_generation = False
    for generation in target.get('generations', []):
        copy_states = []
        for copy_record in generation.get('copies', []):
            jid = copy_record.get('job_id')
            if jid in active_queue:
                st = active_queue[jid]['state']
            elif jid in repair_sacct:
                st = repair_sacct[jid]['state']
            else:
                st = copy_record.get('status', 'UNKNOWN')
            copy_record['slurm_state'] = st
            copy_states.append(st)
        if copy_states and any(st in ACTIVE_STATES for st in copy_states):
            generation['status'] = 'active'
            active_generation = True
        elif len(copy_states) == 2 and all(st not in ACTIVE_STATES for st in copy_states):
            generation['status'] = 'failed_no_complete_output'
    if not active_generation:
        generation = launch_pair(key, target)
        repairs_launched.append({
            'target': key,
            'job_ids': [c['job_id'] for c in generation['copies']],
            'seeds': [c['seed'] for c in generation['copies']],
        })

save_state()

# Refresh queue and compute a per-case progress table.
active_queue = squeue_records()
normal_jobs = parse_normal_submissions()
active_by_result = {}
for jid, q in active_queue.items():
    if q['name'] != 'OBS400' or jid not in normal_jobs:
        continue
    active_by_result[normal_jobs[jid]['result']] = q['state']
repair_active_by_key = {}
for key, target in state['targets'].items():
    n = 0
    for generation in target.get('generations', []):
        for copy_record in generation.get('copies', []):
            if copy_record.get('job_id') in active_queue:
                n += 1
    repair_active_by_key[key] = n

case_stats = {}
for row in rows:
    case = (row['U'], row['V'])
    stat = case_stats.setdefault(case, {
        'U': row['U'], 'V': row['V'], 'total': 0, 'complete': 0,
        'running': 0, 'pending': 0, 'waiting': 0, 'repair_copies': 0,
        'unresolved_failed_targets': 0,
    })
    stat['total'] += 1
    if is_complete(row['result']):
        stat['complete'] += 1
        continue
    ast = active_by_result.get(row['result'])
    if ast == 'RUNNING': stat['running'] += 1
    elif ast: stat['pending'] += 1
    elif row.get('template') and Path(row['template']).is_file(): stat['waiting'] += 1

for key, target in state['targets'].items():
    row = target['row']; case = (row['U'], row['V'])
    if case not in case_stats or is_complete(row['result']):
        continue
    case_stats[case]['repair_copies'] += repair_active_by_key.get(key, 0)
    case_stats[case]['unresolved_failed_targets'] += 1

report = {
    'time': time.strftime('%Y-%m-%d %H:%M:%S'),
    'total_targets': len(rows),
    'complete': sum(x['complete'] for x in case_stats.values()),
    'new_failed_targets': sorted(set(new_failed_targets)),
    'repairs_launched': repairs_launched,
    'winners_installed': winners_installed,
    'siblings_cancelled': siblings_cancelled,
    'cases': list(case_stats.values()),
}
atomic_json(LATEST_REPORT, report)

print('OBS400 progress at {}'.format(report['time']))
print('COMPLETE {}/{} ({:.2f}%)'.format(report['complete'], report['total_targets'],
                                        100.0 * report['complete'] / report['total_targets']))
for stat in case_stats.values():
    pct = 100.0 * stat['complete'] / stat['total']
    print('U={U} V={V}: {complete}/{total} ({pct:.1f}%) | R={running} PD={pending} waiting={waiting} repair_copies={repair_copies} unresolved_failed={unresolved_failed_targets}'.format(
        pct=pct, **stat))
print('NEW_FAILED_TARGETS {}'.format(len(set(new_failed_targets))))
print('REPAIR_PAIRS_LAUNCHED {}'.format(len(repairs_launched)))
for item in repairs_launched:
    print('  {} jobs={} seeds={}'.format(item['target'], ','.join(item['job_ids']), ','.join(str(x) for x in item['seeds'])))
print('WINNERS_INSTALLED {}'.format(len(winners_installed)))
if siblings_cancelled:
    print('SIBLINGS_CANCELLED {}'.format(','.join(siblings_cancelled)))
