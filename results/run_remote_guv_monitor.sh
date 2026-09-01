#!/bin/bash
set -euo pipefail
SOCK=/Users/cosdis/.ssh/cm-9pm@or-login.ornl.gov:22
OUT_JSON="$1"
ssh -S "$SOCK" cades 'cd /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath && python3 -' > "$OUT_JSON" <<'PY'
import csv, glob, json, os, re, shutil, subprocess
from collections import defaultdict
from datetime import datetime

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LAST_RUN_LOCAL = "2026-06-19T00:18:23"
REQUIRED_UV = [(20,3),(20,7),(20,10),(40,14),(40,20),(80,4),(80,8),(80,12),(80,16),(80,18),(80,20),(80,21),(80,24)]
DROPPED_UV = {(80,19),(80,22),(80,28),(80,40),(0,24),(60,0),(100,0),(40,11),(80,32)}
FLOAT_RE = re.compile(r"[-+]?\\d+(?:\\.\\d*)?(?:[Ee][-+]?\\d+)?")
ARGS_RE = re.compile(r"Square_Hubbard_tbc_G_calculation_UV\\.x\\s+(.+)")
UV_RE = re.compile(r"U(-?\\d+)V(-?\\d+)")
DATA_RE = re.compile(r"L4x4Nup8Ndn8U(-?\\d+)V(-?\\d+)tp0f(\\d+)x(\\d+)Q0x0_(Gh|Gp)\\.dat$")

KPOINTS = [(i,0) for i in range(41)] + [(i,i) for i in range(1,41)] + [(40,j) for j in range(1,40)]
assert len(KPOINTS) == 120 and len(set(KPOINTS)) == 120
KSET = set(KPOINTS)


def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True)


def sh_ok(cmd):
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def parse_args(text):
    m = ARGS_RE.search(text)
    if not m:
        return None
    toks = m.group(1).strip().split()
    if len(toks) < 9:
        return None
    try:
        return tuple(int(float(t)) for t in toks[:9])
    except Exception:
        return None


def task_from_args(args):
    return args if args and len(args) >= 9 else None


def read_text(path):
    try:
        with open(path, "r", errors="ignore") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def summarize_file(path):
    info = {"exists": os.path.exists(path), "size": 0, "a_count": None, "b_count": None}
    if not info["exists"]:
        return info
    info["size"] = os.path.getsize(path)
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            if line.startswith("a"):
                info["a_count"] = len(FLOAT_RE.findall(line[1:]))
            elif line.startswith("b"):
                info["b_count"] = len(FLOAT_RE.findall(line[1:]))
    return info


def complete_pair(u,v,kx,ky):
    gh = summarize_file(f"L4x4Nup8Ndn8U{u}V{v}tp0f{kx}x{ky}Q0x0_Gh.dat")
    gp = summarize_file(f"L4x4Nup8Ndn8U{u}V{v}tp0f{kx}x{ky}Q0x0_Gp.dat")
    gh_ok = gh["exists"] and gh["size"] > 1000 and gh["a_count"] == 999 and gh["b_count"] == 999
    gp_ok = gp["exists"] and gp["size"] > 1000 and gp["a_count"] == 999 and gp["b_count"] == 999
    if gh_ok and gp_ok:
        status = "complete"
    elif (not gh["exists"]) and (not gp["exists"]):
        status = "missing"
    else:
        status = "partial"
    return status, gh, gp


def parse_script(path):
    txt = read_text(path)
    args = parse_args(txt)
    task = task_from_args(args)
    return {
        "path": path,
        "args": args,
        "task": task,
        "uv": (task[6], task[7]) if task else None,
        "coord": (task[2], task[3]) if task else None,
        "text": txt,
    }

remote_uv_text = read_text("UVset.txt")
remote_uv_entries = [(int(a), int(b)) for a,b in re.findall(r"\\(([-]?\\d+),([-]?\\d+)\\)", remote_uv_text)]

active = []
sq = sh("squeue -u 9pm -n GUV -h -o '%A|%T|%a|%P|%M|%l|%o'")
for ln in sq.splitlines():
    jobid, state, account, partition, elapsed, timelimit, command = ln.split("|")
    info = parse_script(command)
    info.update({"jobid": jobid, "state": state, "account": account, "partition": partition, "elapsed": elapsed, "timelimit": timelimit, "command": command})
    del info["text"]
    active.append(info)

templates = []
for path in sorted(glob.glob("templates_G_UV/*.sh")):
    info = parse_script(path)
    del info["text"]
    templates.append(info)

uv_reports = []
coord_details = []
coord_status = {}
for u,v in REQUIRED_UV:
    complete = missing = partial = 0
    for kx,ky in KPOINTS:
        status, gh, gp = complete_pair(u,v,kx,ky)
        coord_status[(u,v,kx,ky)] = status
        if status == "complete": complete += 1
        elif status == "missing": missing += 1
        else: partial += 1
        coord_details.append({"u":u,"v":v,"kx":kx,"ky":ky,"status":status,
                              "gh_exists":gh["exists"],"gh_size":gh["size"],"gh_a":gh["a_count"],"gh_b":gh["b_count"],
                              "gp_exists":gp["exists"],"gp_size":gp["size"],"gp_a":gp["a_count"],"gp_b":gp["b_count"]})
    uv_reports.append({"uv":(u,v),"complete":complete,"missing":missing,"partial":partial})

active_by_task = defaultdict(list)
for row in active:
    active_by_task[row["task"]].append(row)
template_by_task = defaultdict(list)
for row in templates:
    template_by_task[row["task"]].append(row)

duplicates = {"active_active": [], "active_template": [], "template_template": []}
for task, rows in active_by_task.items():
    if task and len(rows) > 1:
        duplicates["active_active"].append({"task": task, "jobs": [r["jobid"] for r in rows]})
for task, rows in template_by_task.items():
    if not task:
        continue
    if task in active_by_task:
        duplicates["active_template"].append({"task": task, "jobs": [r["jobid"] for r in active_by_task[task]], "templates": [r["path"] for r in rows]})
    elif len(rows) > 1:
        duplicates["template_template"].append({"task": task, "templates": [r["path"] for r in rows]})

backed_up_templates = []
if duplicates["active_template"] or duplicates["template_template"]:
    backup_dir = f"dedup_templates_G_UV_{TS}"
    os.makedirs(backup_dir, exist_ok=True)
    seen = set()
    for group in duplicates["active_template"]:
        for p in group["templates"]:
            if p not in seen and os.path.exists(p):
                shutil.move(p, os.path.join(backup_dir, os.path.basename(p)))
                backed_up_templates.append({"path": p, "backup_dir": backup_dir})
                seen.add(p)
    for group in duplicates["template_template"]:
        for p in group["templates"][1:]:
            if p not in seen and os.path.exists(p):
                shutil.move(p, os.path.join(backup_dir, os.path.basename(p)))
                backed_up_templates.append({"path": p, "backup_dir": backup_dir})
                seen.add(p)

active_complete_tasks = []
for row in active:
    t = row["task"]
    if t and coord_status.get((t[6],t[7],t[2],t[3])) == "complete":
        active_complete_tasks.append({"jobid": row["jobid"], "task": t})

failed_jobs = []
sacct = sh(f"sacct -u 9pm -S {LAST_RUN_LOCAL} -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,Timelimit,Account,Partition,Submit,Start,End,SubmitLine")
for ln in sacct.splitlines():
    parts = ln.split("|")
    if len(parts) != 12:
        continue
    jobid, jobname, state, exitcode, elapsed, timelimit, account, partition, submit, start, end, submitline = parts
    if jobname != "GUV" or state not in {"FAILED", "TIMEOUT", "CANCELLED", "OUT_OF_MEMORY"}:
        continue
    script_path = submitline.replace("sbatch ", "", 1).strip() if submitline else ""
    script = parse_script(script_path) if script_path else {"task": None, "uv": None, "coord": None, "text": ""}
    slurm_text = read_text(f"slurm-{jobid}.out")
    cause = "unknown"
    if state == "TIMEOUT" or "DUE TO TIME LIMIT" in slurm_text:
        cause = "walltime"
    elif "error while loading shared libraries: libtbb.so.12" in slurm_text:
        cause = "missing_libtbb_env"
    elif "Assertion `m >= 0 && m < maxit' failed" in slurm_text:
        cause = "lanczos_assertion"
    elif exitcode.startswith("127:") and "/locate_E0_20000_fix/" in script.get("text", "") and "/home/9pm/intel/oneapi/tbb/2021.13/lib" not in script.get("text", ""):
        cause = "missing_libtbb_env"
    elif exitcode.startswith("127:"):
        cause = "exec_failure_127"
    failed_jobs.append({
        "jobid": jobid, "state": state, "exitcode": exitcode, "elapsed": elapsed, "timelimit": timelimit,
        "account": account, "partition": partition, "submit": submit, "start": start, "end": end,
        "submitline": submitline, "script_path": script_path, "task": script.get("task"), "uv": script.get("uv"),
        "coord": script.get("coord"), "cause": cause, "slurm_excerpt": "\\n".join(slurm_text.splitlines()[-20:])
    })


def make_resubmit(task, cause, failed_jobid):
    nup, ndn, kx, ky, qx, qy, u, v, tp = task
    exe = "./Square_Hubbard_tbc_G_calculation_UV.x"
    ld = "/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:${LD_LIBRARY_PATH:-}"
    if cause in {"missing_libtbb_env", "lanczos_assertion"}:
        exe = "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath/ccsd_guv_monitor_resubmissions_20260617_064617/locate_E0_20000_fix/Square_Hubbard_tbc_G_calculation_UV.x"
        ld = "/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/2021.13/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}"
    d = f"ccsd_guv_monitor_resubmissions_{TS}"
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"resubmit_{failed_jobid}_U{u}_V{v}_k{kx}x{ky}_{cause}.sh")
    content = f'''#!/bin/bash
#SBATCH -A ccsd
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J GUV
#SBATCH --mem=100G
#SBATCH -t 8:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=cosdis123@gmail.com

cd /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath
export OMP_NUM_THREADS=32
export LD_LIBRARY_PATH={ld}

time {exe} {nup} {ndn} {kx} {ky} {qx} {qy} {u} {v} {tp}
exit $?
'''
    with open(path, 'w') as fh:
        fh.write(content)
    os.chmod(path, 0o755)
    return path

resubmissions = []
skipped_failures = []
required_set = set(REQUIRED_UV)
for row in failed_jobs:
    task = row["task"]
    if not task:
        skipped_failures.append({"jobid": row["jobid"], "reason": "unparsed_task", "cause": row["cause"]})
        continue
    u,v = task[6], task[7]
    kx,ky = task[2], task[3]
    status = coord_status.get((u,v,kx,ky))
    if (u,v) not in required_set:
        skipped_failures.append({"jobid": row["jobid"], "reason": "uv_not_required", "task": task, "cause": row["cause"]})
        continue
    if status == "complete":
        skipped_failures.append({"jobid": row["jobid"], "reason": "data_already_complete", "task": task, "cause": row["cause"]})
        continue
    if active_by_task.get(task):
        skipped_failures.append({"jobid": row["jobid"], "reason": "active_duplicate_exists", "task": task, "active_jobs": [r["jobid"] for r in active_by_task[task]], "cause": row["cause"]})
        continue
    if row["cause"] not in {"walltime", "missing_libtbb_env", "lanczos_assertion"}:
        skipped_failures.append({"jobid": row["jobid"], "reason": "manual_attention", "task": task, "cause": row["cause"]})
        continue
    script_path = make_resubmit(task, row["cause"], row["jobid"])
    rc, stdout, stderr = sh_ok(f"sbatch {script_path}")
    resubmissions.append({"failed_jobid": row["jobid"], "task": task, "cause": row["cause"], "script_path": script_path, "returncode": rc, "stdout": stdout.strip(), "stderr": stderr.strip()})

stray = {"active": [], "templates": [], "data": []}
for row in active:
    if row["uv"] and row["uv"] not in required_set:
        stray["active"].append({"jobid": row["jobid"], "uv": row["uv"], "task": row["task"], "dropped": row["uv"] in DROPPED_UV})
for row in templates:
    if row["uv"] and row["uv"] not in required_set:
        stray["templates"].append({"path": row["path"], "uv": row["uv"], "task": row["task"], "dropped": row["uv"] in DROPPED_UV})
for path in glob.glob("L4x4Nup8Ndn8U*V*tp0f*Q0x0_*.dat"):
    m = DATA_RE.search(path)
    if not m:
        continue
    uv = (int(m.group(1)), int(m.group(2)))
    if uv not in required_set:
        stray["data"].append({"uv": uv, "path": path, "dropped": uv in DROPPED_UV})

report = {
    "timestamp": TS,
    "remote_uvset_entries": remote_uv_entries,
    "uvset_matches_required": remote_uv_entries == REQUIRED_UV,
    "active_running_count": sum(1 for r in active if r["state"] == "RUNNING"),
    "active_pending_count": sum(1 for r in active if r["state"] == "PENDING"),
    "template_count": len(templates),
    "duplicates": duplicates,
    "backed_up_templates": backed_up_templates,
    "uv_reports": uv_reports,
    "coord_details": coord_details,
    "active_complete_tasks": active_complete_tasks,
    "failed_jobs": failed_jobs,
    "resubmissions": resubmissions,
    "skipped_failures": skipped_failures,
    "stray": stray,
    "active_jobs": active,
    "templates": templates,
}
print(json.dumps(report))
PY
