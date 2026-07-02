#!/usr/bin/env python3
"""Render a simple geographic map of the calibration regions + GWC."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Users\jomore\Repos\azure-az-distance-gwc"
OUT = os.path.join(BASE, "diagrams", "region_map.png")

# (label, lat, lon, is_gwc)
PTS = [
    ("Germany West Central\n(Frankfurt) - AZ target", 50.1109, 8.6821, True),
    ("Switzerland North (Zurich)", 47.3769, 8.5417, False),
    ("West Europe (Amsterdam)", 52.3676, 4.9041, False),
    ("France Central (Paris)", 48.8566, 2.3522, False),
    ("North Europe (Dublin)", 53.3498, -6.2603, False),
    ("Sweden Central (Gavle)", 60.6749, 17.1413, False),
]

fig, ax = plt.subplots(figsize=(9, 8))
for label, lat, lon, gwc in PTS:
    color = "#E81123" if gwc else "#0072C6"
    marker = "*" if gwc else "o"
    size = 320 if gwc else 90
    ax.scatter(lon, lat, s=size, color=color, marker=marker, zorder=3,
               edgecolor="black", linewidth=0.5)
    ax.annotate(label, (lon, lat), fontsize=8, xytext=(6, 4),
                textcoords="offset points")
    if not gwc:
        ax.plot([8.6821, lon], [50.1109, lat], color="#999", lw=0.7,
                ls="--", zorder=1)

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Calibration mesh: European Azure regions used as distance anchors\n"
             "(dashed lines = backbone paths measured against Germany West Central)")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT, dpi=140)
print("Wrote", OUT)
