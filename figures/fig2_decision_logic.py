"""Figure 2 - decision logic for parcel-level crop-stress detection (Tip-Tap). Vector PDF + 600 dpi PNG."""
import sys
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch

mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 7})
GRN, BLU, PUR, BRN, RED, GRY = "#00B050", "#0070C0", "#7030A0", "#A0522D", "#FF0000", "#7F7F7F"
FILL = {GRN: "#E8F6EE", BLU: "#E6F0FA", PUR: "#F1E9F7", BRN: "#F6ECE4", RED: "#FDE7E7", GRY: "#F2F2F2", "k": "#FFFFFF"}

fig = plt.figure(figsize=(7.2, 8.6))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(3, 119); ax.set_axis_off()

def box(x, y, w, h, title, body="", col="k", tsize=7.5, bsize=6.5, bold=True, ls="-"):
    ec = "black" if col == "k" else col
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=FILL[col], ec=ec, lw=1.0, ls=ls, zorder=2))
    if body:
        ax.text(x, y + h * 0.18, title, ha="center", va="center", fontsize=tsize, fontweight="bold" if bold else "normal", zorder=3)
        ax.text(x, y - h * 0.20, body, ha="center", va="center", fontsize=bsize, zorder=3, linespacing=1.25)
    else:
        ax.text(x, y, title, ha="center", va="center", fontsize=tsize, fontweight="bold" if bold else "normal", zorder=3, linespacing=1.25)

def diamond(x, y, w, h, text, col="k"):
    ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True,
                         fc="white", ec="black" if col == "k" else col, lw=1.0, zorder=2))
    ax.text(x, y, text, ha="center", va="center", fontsize=6.5, zorder=3, linespacing=1.2)

def arrow(p0, p1, label=None, lpos=0.5, loff=(1.2, 0), col="black", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=8, lw=0.9, color=col, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0, zorder=1))
    if label:
        lx = p0[0] + (p1[0] - p0[0]) * lpos + loff[0]; ly = p0[1] + (p1[1] - p0[1]) * lpos + loff[1]
        ax.text(lx, ly, label, ha="left", va="center", fontsize=6.5, fontweight="bold", color=col, zorder=3)

def line(pts, col="black", ls="-", lw=0.9):
    xs, ys = zip(*pts); ax.plot(xs, ys, color=col, ls=ls, lw=lw, zorder=1, solid_capstyle="butt")

# ---- 1. inputs ---------------------------------------------------------------------------------------------------
box(50, 114, 70, 8, "Parcel time series: 12-day composites, 2019–2025",
    "Sentinel-2 L2A (EVI2, MSAVI2, NDRE, NDMI, MNDWI, SI)   ·   Sentinel-1 GRD IW (VV, VH)")
box(50, 103.5, 70, 7.5, "Robust anomaly for every index",
    r"$z = (x - \mathrm{median}) \,/\, (1.4826 \cdot \mathrm{MAD})$, crop × county × composite climatology, 2019–2022")
arrow((50, 110), (50, 107.25))

# ---- 2. signal groups --------------------------------------------------------------------------------------------
cols = [(14, GRN, "Vigour", "EVI2: primary, z ≤ −1.0\nMSAVI2, NDRE: complementary"),
        (38, BLU, "Water (optical)", "NDMI: corroboration, z ≤ −0.5\nMNDWI: surface water"),
        (62, PUR, "Water (radar)", "ΔVV: corroboration, z ≤ −0.5\n(alternative to NDMI)"),
        (86, BRN, "Soil", "SI, March composites\n→ pre-season salinity class")]
line([(50, 99.75), (50, 97.5)]); line([(14, 97.5), (86, 97.5)])
for x, c, t, b in cols:
    arrow((x, 97.5), (x, 94.6))
    box(x, 90, 21, 9.2, t, b, col=c)
ax.text(86, 83.2, "structural covariate only;\nnot used in detection", ha="center", va="top", fontsize=6, style="italic", color=BRN)

# ---- 3. Tip decisions --------------------------------------------------------------------------------------------
X = 38                                                    # main decision spine
line([(14, 85.4), (14, 81.5), (62, 81.5), (62, 85.4)]); line([(38, 85.4), (38, 81.5)])
arrow((X, 81.5), (X, 78.6))
diamond(X, 74.5, 30, 8.2, "Composite inside the\ncrop growing window?")
diamond(X, 63.5, 30, 8.2, "EVI2 z ≤ −1.0 ?")
diamond(X, 52.5, 30, 8.2, "NDMI z ≤ −0.5\nor ΔVV z ≤ −0.5 ?")
diamond(X, 41.5, 30, 8.2, "Stressed in two\nconsecutive composites?")
for y0, y1 in [(70.4, 67.6), (59.4, 56.6), (48.4, 45.6)]:
    arrow((X, y0), (X, y1), "yes", loff=(1.0, 0))
# "no" exits to the right
NX = 66
for y, txt, c in [(74.5, "not evaluated", GRY), (63.5, "no stress", GRY), (52.5, "unattributed vigour drop", GRY)]:
    arrow((X + 15, y), (NX, y), "no", lpos=0.35, loff=(0, 1.3))
    box(NX + 11, y, 22, 4.6, txt, col=c, tsize=6.5, bold=False)
# not two consecutive -> back to next composite
line([(X - 15, 41.5), (8, 41.5), (8, 74.5)], col=GRY, ls="--")
arrow((8, 74.5), (X - 15, 74.5), col=GRY, ls="--")
ax.text(9, 43.0, "no: next composite", ha="left", va="bottom", fontsize=6, color=GRY, fontweight="bold")

# ---- 4. Tip ------------------------------------------------------------------------------------------------------
arrow((X, 37.4), (X, 34.6), "yes", loff=(1.0, 0))
box(X, 30.5, 56, 8.2, "Tip: confirmed stress episode opens",
    "onset = first of the two composites; operational alert ≈ 12 d later\nacute: two clear composites before onset; chronic: stressed at window start", col=RED)

# ---- 5. Tap / censoring ------------------------------------------------------------------------------------------
arrow((X, 26.4), (X, 23.6))
diamond(X, 19.5, 30, 8.2, "EVI2 z ≥ −0.5 in two\nconsecutive composites?")
arrow((X + 15, 19.5), (NX, 19.5), "yes", lpos=0.35, loff=(0, 1.3))
box(NX + 15, 19.5, 30, 8.2, "Tap: episode recovers",
    "recovery = first of the two composites\nduration in 12-day steps (minimum 24 d)", col=GRN)
arrow((X, 15.4), (X, 12.6), "no", loff=(1.0, 0))
diamond(X, 8.5, 30, 8.2, "Harvest composite\nreached?")
arrow((X + 15, 8.5), (NX, 8.5), "yes", lpos=0.35, loff=(0, 1.3))
box(NX + 15, 8.5, 30, 8.2, "Unresolved at harvest",
    "right-censored; proxy for season-end loss\n(loss itself not observed)", col=GRY)
line([(X - 15, 8.5), (8, 8.5), (8, 19.5)], col=GRY, ls="--")
arrow((8, 19.5), (X - 15, 19.5), col=GRY, ls="--")
ax.text(9, 10.0, "no: next composite", ha="left", va="bottom", fontsize=6, color=GRY, fontweight="bold")

out = sys.argv[1] if len(sys.argv) > 1 else "Fig2_decision_logic"
fig.savefig(out + ".pdf", bbox_inches="tight", pad_inches=0.05); fig.savefig(out + ".png", dpi=600, bbox_inches="tight", pad_inches=0.05); fig.savefig(out + ".svg", bbox_inches="tight", pad_inches=0.05)
print("saved", out)
