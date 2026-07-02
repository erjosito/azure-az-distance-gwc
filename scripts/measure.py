#!/usr/bin/env python3
"""High-sample min-RTT ping measurements across the lab VMs via az run-command.

Phase 1 (calibration): region reps ping each other over PUBLIC IPs (Azure backbone).
Phase 2 (az):          the 4 GWC zone VMs ping each other over PRIVATE IPs (intra-VNet).
Phases are sequential so no VM receives two concurrent run-commands.
Outputs raw-output/latency_raw.csv (min/avg/max RTT per ordered pair).
"""
import subprocess, re, csv, sys, os, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

RG = "lab-azdist-20260702"
BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc\raw-output"
OUT = os.path.join(BASE, "latency_raw.csv")

NODES = {
    "vm-chn":  {"pub": "PUBLIC_IP_REDACTED",  "priv": "10.61.0.4"},
    "vm-weu":  {"pub": "PUBLIC_IP_REDACTED",    "priv": "10.62.0.4"},
    "vm-frc":  {"pub": "PUBLIC_IP_REDACTED",   "priv": "10.63.0.4"},
    "vm-neu":  {"pub": "PUBLIC_IP_REDACTED", "priv": "10.66.0.4"},
    "vm-sec":  {"pub": "PUBLIC_IP_REDACTED",  "priv": "10.67.0.4"},
    "gwc-z1a": {"pub": "PUBLIC_IP_REDACTED",   "priv": "10.60.0.4"},
    "gwc-z1b": {"pub": "PUBLIC_IP_REDACTED",  "priv": "10.60.0.5"},
    "gwc-z2":  {"pub": "PUBLIC_IP_REDACTED",  "priv": "10.60.0.6"},
    "gwc-z3":  {"pub": "PUBLIC_IP_REDACTED",    "priv": "10.60.0.7"},
}
CALIB = ["vm-chn", "vm-weu", "vm-frc", "vm-neu", "vm-sec", "gwc-z1a"]
GWC = ["gwc-z1a", "gwc-z1b", "gwc-z2", "gwc-z3"]
PING = "ping -c 3000 -i 0.002 -q {ip}"

def remote_script(targets, key):
    lines = ["#!/bin/bash"]
    for label, node in targets:
        ip = NODES[node][key]
        lines.append(f'echo -n "{label} "; ({PING.format(ip=ip)} 2>/dev/null | grep rtt) || echo NORTT')
    return "\n".join(lines) + "\n"

def run_source(src, targets, key, transport):
    script = remote_script(targets, key)
    fd, path = tempfile.mkstemp(suffix=".sh", text=True)
    with os.fdopen(fd, "w", newline="\n") as fh:
        fh.write(script)
    try:
        cmd = ["cmd", "/c", "az", "vm", "run-command", "invoke", "-g", RG, "-n", src,
               "--command-id", "RunShellScript", "--scripts", f"@{path}",
               "--query", "value[0].message", "-o", "tsv"]
        p = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        os.unlink(path)
    rows = []
    for line in p.stdout.splitlines():
        m = re.match(r"(\S+)\s+rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", line)
        if m:
            rows.append((src, m.group(1), transport, float(m.group(2)),
                         float(m.group(3)), float(m.group(4)), float(m.group(5))))
    if rows:
        print(f"[OK] {src}: {len(rows)} pairs")
    else:
        print(f"[WARN] {src}: no rtt\n  out={p.stdout[:200]!r}\n  err={p.stderr[:200]!r}", file=sys.stderr)
    return rows

def run_phase(name, sources, key, transport):
    print(f"=== phase {name} ===")
    jobs = [(s, [(d, d) for d in sources if d != s], key, transport) for s in sources]
    rows = []
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = [ex.submit(run_source, *j) for j in jobs]
        for f in as_completed(futs):
            rows.extend(f.result())
    return rows

def main():
    all_rows = []
    all_rows += run_phase("calibration", CALIB, "pub", "backbone-public")
    all_rows += run_phase("az", GWC, "priv", "intra-vnet-private")
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "dst", "transport", "min_ms", "avg_ms", "max_ms", "mdev_ms"])
        w.writerows(sorted(all_rows))
    print(f"\nWrote {len(all_rows)} rows to {OUT}")

if __name__ == "__main__":
    main()
