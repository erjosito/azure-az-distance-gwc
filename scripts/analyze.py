#!/usr/bin/env python3
"""Analyze latency_raw.csv: calibrate RTT-vs-distance on the region backbone mesh,
then infer Germany West Central inter-AZ distances from the intra-VNet floors.

Method
------
1. Great-circle (haversine) distance between region metros.
2. Per region pair, take the pair min-RTT (min of both directions) as the
   propagation floor over the Azure backbone.
3. Linear regression: minRTT_backbone = slope * distance_km + intercept.
   The slope already folds in the fibre refractive index AND the routing
   detour factor (fibre is never laid great-circle), so it maps great-circle
   km straight to RTT.
4. GWC AZ propagation = pairMinRTT(AZ) - pairMinRTT(same-zone baseline).
   Inferred great-circle distance = AZ_propagation / slope.
   Report as an upper bound (same-zone baseline already removes switching/stack).
"""
import csv, os, math, itertools, json

BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc"
RAW = os.path.join(BASE, "raw-output", "latency_raw.csv")
OUT = os.path.join(BASE, "raw-output", "analysis.json")

# Region metro coordinates (Azure region -> datacenter metro, approximate).
METRO = {
    "gwc-z1a": ("Frankfurt",  50.1109,  8.6821),   # Germany West Central
    "vm-chn":  ("Zurich",     47.3769,  8.5417),   # Switzerland North
    "vm-weu":  ("Amsterdam",  52.3676,  4.9041),   # West Europe
    "vm-frc":  ("Paris",      48.8566,  2.3522),   # France Central
    "vm-neu":  ("Dublin",     53.3498, -6.2603),   # North Europe
    "vm-sec":  ("Gavle",      60.6749, 17.1413),   # Sweden Central
}
GWC_ZONES = {"gwc-z1a", "gwc-z1b", "gwc-z2", "gwc-z3"}
BASELINE_PAIR = frozenset({"gwc-z1a", "gwc-z1b"})  # same physical zone (zone 1)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load():
    rows = []
    with open(RAW) as fh:
        for r in csv.DictReader(fh):
            r["min_ms"] = float(r["min_ms"])
            rows.append(r)
    return rows


def pair_min(rows, transport):
    """Collapse both directions to a single min-RTT per unordered pair."""
    best = {}
    for r in rows:
        if r["transport"] != transport:
            continue
        key = frozenset({r["src"], r["dst"]})
        best[key] = min(best.get(key, 1e9), r["min_ms"])
    return best


def linreg(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    yhat = [slope * x + intercept for x in xs]
    ss_res = sum((y - yh) ** 2 for y, yh in zip(ys, yhat))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return slope, intercept, r2


def main():
    rows = load()

    # --- 1. Calibration on the backbone region mesh (public IP pings) ---
    bb = pair_min(rows, "backbone-public")
    calib = []
    for key, rtt in bb.items():
        a, b = tuple(key)
        if a in METRO and b in METRO:
            na, la1, lo1 = METRO[a]
            nb, la2, lo2 = METRO[b]
            d = haversine(la1, lo1, la2, lo2)
            calib.append({"pair": f"{na}-{nb}", "dist_km": round(d, 1),
                          "min_rtt_ms": rtt})
    calib.sort(key=lambda c: c["dist_km"])
    xs = [c["dist_km"] for c in calib]
    ys = [c["min_rtt_ms"] for c in calib]
    slope, intercept, r2 = linreg(xs, ys)

    # Theoretical fibre expectation: RTT us/km one-way ~4.9, round-trip ~9.8
    # => 0.0098 ms/km on straight fibre; real routed slope is higher.
    theo_slope = 0.0098

    print("=== Backbone calibration (region mesh) ===")
    for c in calib:
        pred = slope * c["dist_km"] + intercept
        print(f"  {c['pair']:<22} {c['dist_km']:>7.1f} km  "
              f"minRTT {c['min_rtt_ms']:>6.3f} ms  fit {pred:6.3f}")
    print(f"\n  slope     = {slope*1000:.4f} us/km RTT ({slope:.5f} ms/km)")
    print(f"  intercept = {intercept:.3f} ms")
    print(f"  R^2       = {r2:.4f}")
    print(f"  theoretical straight-fibre slope = {theo_slope:.5f} ms/km")
    print(f"  implied routing detour factor    = {slope/theo_slope:.2f}x")

    # --- 2. GWC inter-AZ inference (private IP intra-VNet pings) ---
    az = pair_min(rows, "intra-vnet-private")
    baseline = az[BASELINE_PAIR]
    print(f"\n=== GWC inter-AZ inference ===")
    print(f"  same-zone baseline (z1a<->z1b) minRTT = {baseline:.3f} ms")

    zone_of = {"gwc-z1a": "z1", "gwc-z1b": "z1", "gwc-z2": "z2", "gwc-z3": "z3"}
    az_results = []
    for key, rtt in az.items():
        a, b = tuple(key)
        za, zb = zone_of[a], zone_of[b]
        if za == zb:
            continue  # same-zone, skip
        prop = rtt - baseline
        dist_gc = prop / slope
        dist_route = prop / theo_slope  # if it were straight fibre = route length
        az_results.append({
            "zones": "-".join(sorted({za, zb})),
            "pair_min_rtt_ms": round(rtt, 3),
            "propagation_ms": round(prop, 3),
            "inferred_gc_km": round(dist_gc, 1),
            "max_fibre_km": round(dist_route, 1),
        })
    # dedupe by zone-pair keeping min
    byzone = {}
    for r in az_results:
        z = r["zones"]
        if z not in byzone or r["pair_min_rtt_ms"] < byzone[z]["pair_min_rtt_ms"]:
            byzone[z] = r
    for z in sorted(byzone):
        r = byzone[z]
        print(f"  {z}: minRTT {r['pair_min_rtt_ms']:.3f} ms, "
              f"prop {r['propagation_ms']:.3f} ms  ->  "
              f"~{r['inferred_gc_km']:.1f} km great-circle "
              f"(<= {r['max_fibre_km']:.1f} km fibre)")

    out = {
        "calibration": {
            "slope_ms_per_km": slope,
            "intercept_ms": intercept,
            "r2": r2,
            "theoretical_slope_ms_per_km": theo_slope,
            "routing_detour_factor": slope / theo_slope,
            "pairs": calib,
        },
        "gwc_az": {
            "baseline_same_zone_ms": baseline,
            "pairs": [byzone[z] for z in sorted(byzone)],
        },
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
