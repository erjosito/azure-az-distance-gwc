#!/usr/bin/env python3
"""France Central figure: measured fibre path vs straight-line estimate,
cross-checked against the documented La Courneuve to Les Ulis campus separation."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc"
A = json.load(open(os.path.join(BASE, "raw-output", "analysis_frc.json")))
OUT = os.path.join(BASE, "diagrams", "frc_validation.png")

pairs = A["pairs"]
labels = [p["pair"].replace("zone", "Z").replace("-", " to ") for p in pairs]
# Detour calibrated from public records: 100 km fibre (widest pair) reconciles
# with the documented ~32 km straight-line La Courneuve <-> Les Ulis separation.
DETOUR = 3.13
DOC_KM = 32.0
fib = [p["dist_straight_fibre_km"] for p in pairs]      # fibre-path length (km)
straight = [v / DETOUR for v in fib]                     # straight-line estimate (km)
x = np.arange(len(labels))
w = 0.36

fig, ax = plt.subplots(figsize=(9, 6))
ax.bar(x - w/2, fib, w, label="Measured fibre path (latency)", color="#0072C6")
ax.bar(x + w/2, straight, w, label="Straight-line estimate (fibre / ~3x detour)", color="#7FBA00")
for i, v in enumerate(fib):
    ax.text(i - w/2, v + 1, f"{v:.0f}", ha="center", fontsize=8)
for i, v in enumerate(straight):
    ax.text(i + w/2, v + 1, f"{v:.0f}", ha="center", fontsize=8)

ax.axhline(DOC_KM, color="#E81123", ls="--", lw=1.5,
           label=f"Documented straight-line (La Courneuve to Les Ulis) ~ {DOC_KM:.0f} km")
ax.annotate("public records:\n~32 km straight-line\n(latency = ~100 km of fibre)",
            xy=(2 + w/2, straight[2]), xytext=(0.7, DOC_KM + 30),
            arrowprops=dict(arrowstyle="->", color="#E81123"), fontsize=9, color="#E81123")

ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Distance between zones (km)")
ax.set_title("France Central inter-AZ: latency measures fibre path, not straight-line\n"
             "Records place the widest pair ~32 km apart; latency rides ~100 km of fibre (~3x detour)")
ax.legend(loc="upper left", fontsize=9)
ax.grid(True, axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT, dpi=140)
print("Wrote", OUT)
