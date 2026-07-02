#!/usr/bin/env python3
"""France Central inter-AZ analysis + public-records cross-check.

Reads latency_frc_raw.csv, computes each zone pair's propagation floor against
the appropriate same-zone baseline, and converts to a FIBRE-PATH length using
the speed of light in single-mode fibre (0.0098 ms/km RTT). Latency measures the
network/fibre path, not the straight-line distance.

To recover straight-line distance we need a routing detour factor. Public records
(Journal du Net 2022 + PeeringDB) place the two France Central campuses at
La Courneuve (north Paris) and Les Ulis (south-west Paris), ~32 km apart in a
straight line. The widest measured pair rides ~100 km of fibre, so the detour is
~100/32 ~ 3.1x. That single anchor is applied to the other pairs to estimate
their straight-line separation. Correspondence of logical zones to campuses is
assumed (widest measured pair = widest documented pair), not proven.
"""
import csv, os, json

BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc"
RAW = os.path.join(BASE, "raw-output", "latency_frc_raw.csv")
CAL = os.path.join(BASE, "raw-output", "analysis.json")
OUT = os.path.join(BASE, "raw-output", "analysis_frc.json")

# Documented straight-line separation, La Courneuve <-> Les Ulis (great circle
# of PeeringDB coordinates 48.931N/2.397E and 48.675N/2.196E).
DOC_STRAIGHT_Z2Z3_KM = 32.1
THEO_SLOPE = 0.0098           # ms/km RTT, straight single-mode fibre


def load_pairs():
    best = {}
    with open(RAW) as fh:
        for r in csv.DictReader(fh):
            key = frozenset({r["src"], r["dst"]})
            best[key] = min(best.get(key, 1e9), float(r["min_ms"]))
    return best


def main():
    emp_slope = json.load(open(CAL))["calibration"]["slope_ms_per_km"]
    p = load_pairs()

    base_x64 = p[frozenset({"d-z1a", "d-z1b"})]     # x64 same-zone floor
    base_arm = p[frozenset({"p-z1a", "p-z1b"})]     # arm same-zone floor
    base_mix = p[frozenset({"d-z1a", "p-z1a"})]     # mixed-arch same-zone floor

    pairs = [
        ("zone1-zone2", p[frozenset({"d-z1a", "d-z2"})], base_x64, "x64 (D2d_v4)"),
        ("zone1-zone3", p[frozenset({"p-z1a", "p-z3"})], base_arm, "arm (D2ps_v6)"),
        ("zone2-zone3", p[frozenset({"d-z2", "p-z3"})], base_mix, "mixed x64<->arm"),
    ]

    print("=== France Central inter-AZ (baselines) ===")
    print(f"  x64 same-zone floor   = {base_x64:.3f} ms")
    print(f"  arm same-zone floor   = {base_arm:.3f} ms")
    print(f"  mixed same-zone floor = {base_mix:.3f} ms")
    print(f"  backbone-empirical slope = {emp_slope:.5f} ms/km RTT")
    print(f"  straight-fibre slope     = {THEO_SLOPE:.5f} ms/km RTT\n")

    results = []
    print(f"  {'pair':<12}{'minRTT':>8}{'prop':>8}{'fibre km':>10}  path")
    for name, rtt, base, path in pairs:
        prop = rtt - base
        d_fib = prop / THEO_SLOPE          # fibre-path length (km)
        d_emp = prop / emp_slope           # kept for reference (backbone slope)
        results.append({"pair": name, "min_rtt_ms": round(rtt, 3),
                        "baseline_ms": round(base, 3), "propagation_ms": round(prop, 3),
                        "dist_backbone_slope_km": round(d_emp, 1),
                        "dist_straight_fibre_km": round(d_fib, 1), "path": path})
        print(f"  {name:<12}{rtt:>8.3f}{prop:>8.3f}{d_fib:>10.1f}  {path}")

    z2z3 = next(r for r in results if r["pair"] == "zone2-zone3")
    fibre_z2z3 = z2z3["dist_straight_fibre_km"]
    detour = fibre_z2z3 / DOC_STRAIGHT_Z2Z3_KM
    print(f"\n=== Public-records cross-check (La Courneuve <-> Les Ulis ~ "
          f"{DOC_STRAIGHT_Z2Z3_KM:.0f} km straight-line) ===")
    print(f"  widest-pair fibre path    = {fibre_z2z3:.1f} km (from latency)")
    print(f"  documented straight-line  = {DOC_STRAIGHT_Z2Z3_KM:.1f} km (JDN 2022 + PeeringDB)")
    print(f"  => AZ routing detour      ~ {detour:.2f}x "
          f"(long-haul backbone was {emp_slope/THEO_SLOPE:.2f}x)")
    print("\n  straight-line estimates (fibre / detour):")
    for r in results:
        r["straight_line_est_km"] = round(r["dist_straight_fibre_km"] / detour, 1)
        print(f"    {r['pair']:<12} fibre {r['dist_straight_fibre_km']:>6.1f} km  "
              f"-> straight-line ~ {r['straight_line_est_km']:>5.1f} km")

    json.dump({
        "documented_straight_line_z2z3_km": DOC_STRAIGHT_Z2Z3_KM,
        "backbone_empirical_slope_ms_per_km": emp_slope,
        "straight_fibre_slope_ms_per_km": THEO_SLOPE,
        "az_routing_detour_factor": round(detour, 2),
        "note": ("Latency measures fibre path; detour calibrated from one documented "
                 "campus pair. Zone-to-campus correspondence assumed, not proven."),
        "pairs": results,
    }, open(OUT, "w"), indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
