#!/usr/bin/env python3
"""Supplemental FRC pairs to close the zone 2 <-> zone 3 gap.

The main run used two disjoint SKU sets, so z2 (x64 d-z2) and z3 (arm p-z3)
were never compared. They share the subnet, so we can ping them directly.
To subtract a fair non-distance floor for a mixed x64<->arm path we also
measure d-z1a <-> p-z1a (both in zone 1, one x64 one arm): that IS the
empirical mixed-arch same-zone baseline.
Appends to raw-output/latency_frc_raw.csv.
"""
import subprocess, re, csv, sys, os, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

RG = "lab-azdist-20260702"
BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc\raw-output"
OUT = os.path.join(BASE, "latency_frc_raw.csv")
PRIV = {"d-z2": "10.63.0.10", "p-z3": "10.63.0.7",
        "d-z1a": "10.63.0.8", "p-z1a": "10.63.0.5"}
PING = "ping -c 3000 -i 0.002 -q {ip}"
# (src, dst) ordered pairs to run
PAIRS = [("d-z2", "p-z3"), ("p-z3", "d-z2"),      # z2 <-> z3
         ("d-z1a", "p-z1a"), ("p-z1a", "d-z1a")]  # mixed same-zone baseline


def run(src, dst):
    script = f'#!/bin/bash\necho -n "{dst} "; ({PING.format(ip=PRIV[dst])} 2>/dev/null | grep rtt) || echo NORTT\n'
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
    for line in p.stdout.splitlines():
        m = re.match(r"(\S+)\s+rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", line)
        if m:
            print(f"[OK] {src}->{dst}: min {m.group(2)} ms")
            return (src, dst, "intra-vnet-private", float(m.group(2)),
                    float(m.group(3)), float(m.group(4)), float(m.group(5)))
    print(f"[WARN] {src}->{dst}: no rtt err={p.stderr[:150]!r}", file=sys.stderr)
    return None


def main():
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run, s, d): (s, d) for s, d in PAIRS}
        for f in as_completed(futs):
            r = f.result()
            if r:
                rows.append(r)
    existing = []
    if os.path.exists(OUT):
        with open(OUT) as fh:
            existing = list(csv.reader(fh))[1:]
    keyset = {(r[0], r[1]) for r in existing}
    merged = existing + [list(map(str, r)) for r in rows if (r[0], r[1]) not in keyset]
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "dst", "transport", "min_ms", "avg_ms", "max_ms", "mdev_ms"])
        w.writerows(sorted(merged))
    print(f"\nAppended {len(rows)} rows; total {len(merged)} in {OUT}")


if __name__ == "__main__":
    main()
