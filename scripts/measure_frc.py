#!/usr/bin/env python3
"""France Central inter-AZ min-RTT mesh (validation run).

Two disjoint SKU sets (each with its own same-zone baseline), so we can reach
every zone despite per-zone capacity restrictions:
  ARM set  (D2ps_v6): p-z1a, p-z1b (zone 1), p-z3 (zone 3)  -> zone1<->zone3
  x64 set  (D2d_v4):  d-z1a, d-z1b (zone 1), d-z2 (zone 2)  -> zone1<->zone2
Each VM pings only the other members of its own set over private IPs
(intra-VNet, no NAT). All sources run concurrently (no VM overlap).
Writes raw-output/latency_frc_raw.csv.
"""
import subprocess, re, csv, sys, os, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

RG = "lab-azdist-20260702"
BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc\raw-output"
OUT = os.path.join(BASE, "latency_frc_raw.csv")

NODES = {
    "p-z1a": {"priv": "10.63.0.5", "zone": "1", "sku": "D2ps_v6"},
    "p-z1b": {"priv": "10.63.0.6", "zone": "1", "sku": "D2ps_v6"},
    "p-z3":  {"priv": "10.63.0.7", "zone": "3", "sku": "D2ps_v6"},
    "d-z1a": {"priv": "10.63.0.8", "zone": "1", "sku": "D2d_v4"},
    "d-z1b": {"priv": "10.63.0.9", "zone": "1", "sku": "D2d_v4"},
    "d-z2":  {"priv": "10.63.0.10", "zone": "2", "sku": "D2d_v4"},
}
SETS = {
    "arm": ["p-z1a", "p-z1b", "p-z3"],
    "x64": ["d-z1a", "d-z1b", "d-z2"],
}
PING = "ping -c 3000 -i 0.002 -q {ip}"


def remote_script(targets):
    lines = ["#!/bin/bash"]
    for node in targets:
        ip = NODES[node]["priv"]
        lines.append(f'echo -n "{node} "; ({PING.format(ip=ip)} 2>/dev/null | grep rtt) || echo NORTT')
    return "\n".join(lines) + "\n"


def run_source(src, targets):
    fd, path = tempfile.mkstemp(suffix=".sh", text=True)
    with os.fdopen(fd, "w", newline="\n") as fh:
        fh.write(remote_script(targets))
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
            rows.append((src, m.group(1), "intra-vnet-private", float(m.group(2)),
                         float(m.group(3)), float(m.group(4)), float(m.group(5))))
    if rows:
        print(f"[OK] {src}: {len(rows)} pairs")
    else:
        print(f"[WARN] {src}: no rtt\n  out={p.stdout[:200]!r}\n  err={p.stderr[:200]!r}", file=sys.stderr)
    return rows


def main():
    jobs = []
    for members in SETS.values():
        for s in members:
            jobs.append((s, [d for d in members if d != s]))
    rows = []
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = [ex.submit(run_source, *j) for j in jobs]
        for f in as_completed(futs):
            rows.extend(f.result())
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "dst", "transport", "min_ms", "avg_ms", "max_ms", "mdev_ms"])
        w.writerows(sorted(rows))
    print(f"\nWrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
