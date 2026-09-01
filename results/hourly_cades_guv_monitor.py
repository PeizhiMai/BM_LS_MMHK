#!/usr/bin/env python3
import csv, json, os, re, shlex, subprocess, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REMOTE_DIR = "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath"
SOCK = "/Users/cosdis/.ssh/cm-9pm@or-login.ornl.gov:22"
RESULTS_DIR = Path("/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/results")
LAST_RUN_LOCAL = os.environ.get("LAST_RUN_LOCAL", "2026-06-19T00:18:23")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REQUIRED_UV = [(20,3),(20,7),(20,10),(40,14),(40,20),(80,4),(80,8),(80,12),(80,16),(80,18),(80,20),(80,21),(80,24)]
DROPPED_UV = {(80,19),(80,22),(80,28),(80,40),(0,24),(60,0),(100,0),(40,11),(80,32)}

FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?")
ARGS_RE = re.compile(r"Square_Hubbard_tbc_G_calculation_UV\.x\s+(.+)")
UV_RE = re.compile(r"U(-?\d+)V(-?\d+)")
FK_RE = re.compile(r"f(\d+)x(\d+)Q")


def ssh(cmd: str) -> str:
    res = subprocess.run(["ssh", "-S", SOCK, "cades", cmd], check=True, text=True, capture_output=True)
    return res.stdout


def ssh_no_check(cmd: str):
    return subprocess.run(["ssh", "-S", SOCK, "cades", cmd], check=False, text=True, capture_output=True)


def q(s: str) -> str:
    return shlex.quote(s)


def kpoints():
    pts = []
    pts.extend((i, 0) for i in range(41))
    pts.extend((i, i) for i in range(1, 41))
    pts.extend((40, j) for j in range(1, 40))
    assert len(pts) == 120 and len(set(pts)) == 120
    return pts

KPOINTS = kpoints()
KSET = set(KPOINTS)


def parse_args(text: str):
    m = ARGS_RE.search(text)
    if not m:
        return None
    tokens = m.group(1).strip().split()
    if len(tokens) < 9:
        return None
    try:
        vals = [int(float(tok)) for tok in tokens[:9]]
    except Exception:
        return None
    return tuple(vals)


def task_from_args(args):
    if not args or len(args) < 9:
        return None
    nup, ndn, kx, ky, qx, qy, u, v, tp = args[:9]
    return (nup, ndn, kx, ky, qx, qy, u, v, tp)


def uv_from_task(task):
    return (task[6], task[7]) if task else None


def coord_from_task(task):
    return (task[2], task[3]) if task else None


def parse_data_file(path: str):
    cmd = (
        f"cd {q(REMOTE_DIR)} && python3 - <<'PY' {q(path)}\n"
        "import json, os, re, sys\n"
        "path=sys.argv[1]\n"
        "res={'exists': os.path.exists(path)}\n"
        "if res['exists']:\n"
        "    res['size']=os.path.getsize(path)\n"
        "    a_count=b_count=None\n"
        "    with open(path,'r',errors='ignore') as fh:\n"
        "        for line in fh:\n"
        "            if line.startswith('a'):\n"
        "                a_count=len(re.findall(r'[-+]?\\d+(?:\\.\\d*)?(?:[Ee][-+]?\\d+)?', line[1:]))\n"
        "            elif line.startswith('b'):\n"
        "                b_count=len(re.findall(r'[-+]?\\d+(?:\\.\\d*)?(?:[Ee][-+]?\\d+)?', line[1:]))\n"
        "    res['a_count']=a_count\n"
        "    res['b_count']=b_count\n"
        "print(json.dumps(res))\n"
        "PY"
    )
    out = ssh(cmd)
    return json.loads(out)


def fname(u, v, kx, ky, kind):
    return f"L4x4Nup8Ndn8U{u}V{v}tp0f{kx}x{ky}Q0x0_{kind}.dat"


def read_text(path: str):
    return ssh(f"python3 - <<'PY' {q(path)}\nimport pathlib, sys\np=pathlib.Path(sys.argv[1])\nprint(p.read_text(errors='ignore') if p.exists() else '')\nPY")


def list_templates():
    out = ssh(f"cd {q(REMOTE_DIR)} && find templates_G_UV -maxdepth 1 -type f -name '*.sh' | sort")
    return [ln for ln in out.splitlines() if ln.strip()]


def active_jobs():
    out = ssh(f"squeue -u 9pm -n GUV -h -o '%A|%T|%a|%P|%M|%l|%o'")
    rows = []
    for ln in out.splitlines():
        parts = ln.split("|")
        if len(parts) != 7:
            continue
        jobid, state, account, partition, elapsed, timelimit, command = parts
        text = read_text(command)
        args = parse_args(text)
        rows.append({
            "jobid": jobid, "state": state, "account": account, "partition": partition,
            "elapsed": elapsed, "timelimit": timelimit, "command": command, "args": args,
            "task": task_from_args(args), "uv": uv_from_task(task_from_args(args)), "coord": coord_from_task(task_from_args(args))
        })
    return rows


def templates_info(paths):
    out = []
    for path in paths:
        text = read_text(path)
        args = parse_args(text)
        task = task_from_args(args)
        out.append({"path": path, "args": args, "task": task, "uv": uv_from_task(task), "coord": coord_from_task(task)})
    return out


def sacct_failed():
    out = ssh(f"sacct -u 9pm -S {LAST_RUN_LOCAL} -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,Timelimit,Account,Partition,Submit,Start,End,SubmitLine")
    rows = []
    for ln in out.splitlines():
        parts = ln.split("|")
        if len(parts) != 12:
            continue
        jobid, jobname, state, exitcode, elapsed, timelimit, account, partition, submit, start, end, submitline = parts
        if jobname != 'GUV' or state not in {'FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'}:
            continue
        script_path = submitline.removeprefix('sbatch ').strip() if submitline else ''
        text = read_text(script_path) if script_path else ''
        args = parse_args(text)
        task = task_from_args(args)
        uv = uv_from_task(task)
        coord = coord_from_task(task)
        slurm_path = f"{REMOTE_DIR}/slurm-{jobid}.out"
        slurm = read_text(slurm_path)
        cause = 'unknown'
        if state == 'TIMEOUT' or 'DUE TO TIME LIMIT' in slurm:
            cause = 'walltime'
        elif 'error while loading shared libraries: libtbb.so.12' in slurm:
            cause = 'missing_libtbb_env'
        elif 'Assertion `m >= 0 && m < maxit' in slurm:
            cause = 'lanczos_assertion'
        elif exitcode.startswith('127:'):
            if '/locate_E0_20000_fix/' in text and '/home/9pm/intel/oneapi/tbb/2021.13/lib' not in text:
                cause = 'missing_libtbb_env'
            else:
                cause = 'exec_failure_127'
        rows.append({
            'jobid': jobid, 'state': state, 'exitcode': exitcode, 'elapsed': elapsed, 'timelimit': timelimit,
            'account': account, 'partition': partition, 'submit': submit, 'start': start, 'end': end,
            'submitline': submitline, 'script_path': script_path, 'args': args, 'task': task, 'uv': uv,
            'coord': coord, 'cause': cause, 'slurm_excerpt': '\n'.join(slurm.splitlines()[-20:])
        })
    return rows


def uvset_remote_text():
    return ssh(f"cd {q(REMOTE_DIR)} && cat UVset.txt")


def uvset_remote_entries(text: str):
    return [(int(a), int(b)) for a, b in re.findall(r"\(([-]?\d+),([-]?\d+)\)", text)]


def data_uv_inventory():
    out = ssh(f"cd {q(REMOTE_DIR)} && find . -maxdepth 1 -type f -name 'L4x4Nup8Ndn8U*V*tp0f*Q0x0_*.dat' | sed 's#^./##' | sort")
    uv_map = defaultdict(int)
    for f in out.splitlines():
        m = UV_RE.search(f)
        if m:
            uv_map[(int(m.group(1)), int(m.group(2)))] += 1
    return uv_map


def completeness_for_uv(u, v):
    rows = []
    complete = 0
    missing = 0
    partial = 0
    for kx, ky in KPOINTS:
        gh = parse_data_file(fname(u, v, kx, ky, 'Gh'))
        gp = parse_data_file(fname(u, v, kx, ky, 'Gp'))
        gh_ok = gh.get('exists') and gh.get('size', 0) > 1000 and gh.get('a_count') == 999 and gh.get('b_count') == 999
        gp_ok = gp.get('exists') and gp.get('size', 0) > 1000 and gp.get('a_count') == 999 and gp.get('b_count') == 999
        if gh_ok and gp_ok:
            status = 'complete'
            complete += 1
        elif (not gh.get('exists')) and (not gp.get('exists')):
            status = 'missing'
            missing += 1
        else:
            status = 'partial'
            partial += 1
        rows.append({'u': u, 'v': v, 'kx': kx, 'ky': ky, 'status': status,
                     'gh_exists': gh.get('exists', False), 'gh_size': gh.get('size', 0), 'gh_a': gh.get('a_count'), 'gh_b': gh.get('b_count'),
                     'gp_exists': gp.get('exists', False), 'gp_size': gp.get('size', 0), 'gp_a': gp.get('a_count'), 'gp_b': gp.get('b_count')})
    return {'uv': (u, v), 'complete': complete, 'missing': missing, 'partial': partial, 'rows': rows}


def write_remote_script(path: str, content: str):
    quoted = q(content)
    ssh(f"python3 - <<'PY' {q(path)} {quoted}\nimport os, pathlib, sys\npath=pathlib.Path(sys.argv[1]); content=sys.argv[2]\npath.parent.mkdir(parents=True, exist_ok=True)\npath.write_text(content)\nos.chmod(path,0o755)\nPY")


def sbatch_remote(path: str):
    res = ssh_no_check(f"cd {q(REMOTE_DIR)} && sbatch {q(path)}")
    return {'returncode': res.returncode, 'stdout': res.stdout.strip(), 'stderr': res.stderr.strip()}


def make_resubmit_script(task, cause, original_jobid):
    nup, ndn, kx, ky, qx, qy, u, v, tp = task
    exe = f"{REMOTE_DIR}/Square_Hubbard_tbc_G_calculation_UV.x"
    ld = "/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:${LD_LIBRARY_PATH:-}"
    if cause in {'missing_libtbb_env', 'lanczos_assertion'}:
        exe = f"{REMOTE_DIR}/ccsd_guv_monitor_resubmissions_20260617_064617/locate_E0_20000_fix/Square_Hubbard_tbc_G_calculation_UV.x"
        ld = "/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/2021.13/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}"
    lines = [
        "#!/bin/bash",
        "#SBATCH -A ccsd",
        "#SBATCH -p burst",
        "#SBATCH -N 1",
        "#SBATCH -n 32",
        "#SBATCH -c 1",
        "#SBATCH -J GUV",
        "#SBATCH --mem=100G",
        "#SBATCH -t 8:00:00",
        "#SBATCH --mail-type=ALL",
        "#SBATCH --mail-user=cosdis123@gmail.com",
        f"cd {REMOTE_DIR}",
        "export OMP_NUM_THREADS=32",
        f"export LD_LIBRARY_PATH={ld}",
        f"time {exe} {nup} {ndn} {kx} {ky} {qx} {qy} {u} {v} {tp}",
        "exit $?",
    ]
    basename = f"resubmit_{original_jobid}_U{u}_V{v}_k{kx}x{ky}_{cause}_{TS}.sh"
    dir_path = f"{REMOTE_DIR}/ccsd_guv_monitor_resubmissions_{TS}"
    return f"{dir_path}/{basename}", "\n".join(lines) + "\n"


def main():
    remote_uv_text = uvset_remote_text()
    remote_uv_entries = uvset_remote_entries(remote_uv_text)
    active = active_jobs()
    templates = templates_info(list_templates())
    data_inv = data_uv_inventory()
    uv_reports = [completeness_for_uv(u, v) for u, v in REQUIRED_UV]
    coord_status = {(r['uv'][0], r['uv'][1], row['kx'], row['ky']): row['status'] for r in uv_reports for row in r['rows']}

    active_by_task = defaultdict(list)
    for row in active:
        active_by_task[row['task']].append(row)
    template_by_task = defaultdict(list)
    for row in templates:
        template_by_task[row['task']].append(row)

    duplicates = {'active_active': [], 'active_template': [], 'template_template': []}
    for task, rows in active_by_task.items():
        if task and len(rows) > 1:
            duplicates['active_active'].append({'task': task, 'jobs': [r['jobid'] for r in rows]})
    for task, trows in template_by_task.items():
        if not task:
            continue
        if task in active_by_task:
            duplicates['active_template'].append({'task': task, 'jobs': [r['jobid'] for r in active_by_task[task]], 'templates': [r['path'] for r in trows]})
        elif len(trows) > 1:
            duplicates['template_template'].append({'task': task, 'templates': [r['path'] for r in trows]})

    backed_up_templates = []
    if duplicates['active_template'] or duplicates['template_template']:
        backup_dir = f"{REMOTE_DIR}/dedup_templates_G_UV_{TS}"
        ssh(f"mkdir -p {q(backup_dir)}")
        seen = set()
        for group in duplicates['active_template'] + duplicates['template_template']:
            paths = list(group.get('templates', []))
            if group in duplicates['template_template'] and len(paths) > 1:
                paths = paths[1:]
            for path in paths:
                if path in seen:
                    continue
                ssh(f"mv {q(path)} {q(backup_dir)}/")
                backed_up_templates.append({'path': path, 'backup_dir': backup_dir})
                seen.add(path)

    active_complete = []
    for row in active:
        task = row['task']
        if task:
            key = (task[6], task[7], task[2], task[3])
            if coord_status.get(key) == 'complete':
                active_complete.append({'jobid': row['jobid'], 'task': task})

    failed = sacct_failed()
    resubmissions = []
    skipped_failures = []
    for row in failed:
        task = row['task']
        if not task:
            skipped_failures.append({'jobid': row['jobid'], 'reason': 'unparsed_task', 'cause': row['cause']})
            continue
        uv = (task[6], task[7])
        coord = (task[2], task[3])
        status = coord_status.get((uv[0], uv[1], coord[0], coord[1]))
        if uv not in REQUIRED_UV:
            skipped_failures.append({'jobid': row['jobid'], 'reason': 'uv_not_required', 'task': task, 'cause': row['cause']})
            continue
        if status == 'complete':
            skipped_failures.append({'jobid': row['jobid'], 'reason': 'data_already_complete', 'task': task, 'cause': row['cause']})
            continue
        if active_by_task.get(task):
            skipped_failures.append({'jobid': row['jobid'], 'reason': 'active_duplicate_exists', 'task': task, 'active_jobs': [j['jobid'] for j in active_by_task[task]], 'cause': row['cause']})
            continue
        if row['cause'] not in {'walltime', 'missing_libtbb_env', 'lanczos_assertion'}:
            skipped_failures.append({'jobid': row['jobid'], 'reason': 'manual_attention', 'task': task, 'cause': row['cause']})
            continue
        script_path, content = make_resubmit_script(task, row['cause'], row['jobid'])
        write_remote_script(script_path, content)
        submit = sbatch_remote(script_path)
        resubmissions.append({'failed_jobid': row['jobid'], 'task': task, 'cause': row['cause'], 'script_path': script_path, 'submit': submit})
        if submit['returncode'] == 0:
            active_by_task[task].append({'jobid': submit['stdout'], 'task': task})

    stray = {'active': [], 'templates': [], 'data': []}
    required_set = set(REQUIRED_UV)
    for row in active:
        if row['uv'] and row['uv'] not in required_set:
            stray['active'].append({'jobid': row['jobid'], 'uv': row['uv'], 'task': row['task'], 'dropped': row['uv'] in DROPPED_UV})
    for row in templates:
        if row['uv'] and row['uv'] not in required_set:
            stray['templates'].append({'path': row['path'], 'uv': row['uv'], 'task': row['task'], 'dropped': row['uv'] in DROPPED_UV})
    for uv, count in sorted(data_inv.items()):
        if uv not in required_set:
            stray['data'].append({'uv': uv, 'file_count': count, 'dropped': uv in DROPPED_UV})

    report = {
        'timestamp': TS,
        'remote_uvset_entries': remote_uv_entries,
        'uvset_matches_required': remote_uv_entries == REQUIRED_UV,
        'active_running_count': sum(1 for r in active if r['state'] == 'RUNNING'),
        'active_pending_count': sum(1 for r in active if r['state'] == 'PENDING'),
        'template_count': len(templates),
        'duplicates': duplicates,
        'backed_up_templates': backed_up_templates,
        'uv_reports': [{'uv': r['uv'], 'complete': r['complete'], 'missing': r['missing'], 'partial': r['partial']} for r in uv_reports],
        'active_complete_tasks': active_complete,
        'failed_jobs': failed,
        'resubmissions': resubmissions,
        'skipped_failures': skipped_failures,
        'stray': stray,
        'active_jobs': active,
        'templates': templates,
        'coord_details': [row for r in uv_reports for row in r['rows']],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"hourly_cades_guv_monitor_{TS}.json"
    tsv_path = RESULTS_DIR / f"hourly_cades_guv_monitor_uv_{TS}.tsv"
    coord_tsv = RESULTS_DIR / f"hourly_cades_guv_monitor_coords_{TS}.tsv"
    failed_tsv = RESULTS_DIR / f"hourly_cades_guv_monitor_failed_{TS}.tsv"
    json_path.write_text(json.dumps(report, indent=2))
    with tsv_path.open('w', newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        w.writerow(['U','V','complete','missing','partial'])
        for r in report['uv_reports']:
            u,v = r['uv']
            w.writerow([u,v,r['complete'],r['missing'],r['partial']])
    with coord_tsv.open('w', newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        w.writerow(['U','V','kx','ky','status','gh_exists','gh_size','gh_a','gh_b','gp_exists','gp_size','gp_a','gp_b'])
        for row in report['coord_details']:
            w.writerow([row['u'],row['v'],row['kx'],row['ky'],row['status'],row['gh_exists'],row['gh_size'],row['gh_a'],row['gh_b'],row['gp_exists'],row['gp_size'],row['gp_a'],row['gp_b']])
    with failed_tsv.open('w', newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        w.writerow(['jobid','state','exitcode','cause','U','V','kx','ky','script_path'])
        for row in failed:
            task = row['task'] or ('','','','','','','','','')
            w.writerow([row['jobid'],row['state'],row['exitcode'],row['cause'],task[6],task[7],task[2],task[3],row['script_path']])
    print(json.dumps({'json_path': str(json_path), 'uv_tsv': str(tsv_path), 'coord_tsv': str(coord_tsv), 'failed_tsv': str(failed_tsv), 'report': report}))

if __name__ == '__main__':
    main()
