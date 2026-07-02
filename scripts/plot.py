#!/usr/bin/env python3
"""Render the RTT-vs-distance regression plot from analysis.json."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc"
A = json.load(open(os.path.join(BASE, "raw-output", "analysis.json")))
OUT = os.path.join(BASE, "diagrams", "latency_vs_distance.png")

cal = A["calibration"]
slope, intercept, r2 = cal["slope_ms_per_km"], cal["intercept_ms"], cal["r2"]
xs = [p["dist_km"] for p in cal["pairs"]]
ys = [p["min_rtt_ms"] for p in cal["pairs"]]

fig, ax = plt.subplots(figsize=(9, 6))
ax.scatter(xs, ys, s=60, color="#0072C6", zorder=3, label="Region pair (min RTT)")
for p in cal["pairs"]:
    ax.annotate(p["pair"], (p["dist_km"], p["min_rtt_ms"]),
                fontsize=7, xytext=(4, 4), textcoords="offset points")

xline = [0, max(xs) * 1.05]
yline = [slope * x + intercept for x in xline]
ax.plot(xline, yline, "--", color="#E81123", zorder=2,
        label=f"Fit: RTT = {slope*1000:.2f} us/km * d + {intercept:.2f} ms  (R2={r2:.3f})")

# theoretical straight-fibre line
theo = cal["theoretical_slope_ms_per_km"]
ax.plot(xline, [theo * x + intercept for x in xline], ":", color="#888",
        label=f"Straight-fibre floor ({theo*1000:.2f} us/km)")

ax.set_xlabel("Great-circle distance between region metros (km)")
ax.set_ylabel("Minimum round-trip time (ms)")
ax.set_title("Azure backbone: min RTT vs great-circle distance (European region mesh)")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=9)
fig.tight_layout()
fig.savefig(OUT, dpi=140)
print("Wrote", OUT)
