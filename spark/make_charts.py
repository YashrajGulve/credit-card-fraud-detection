import json, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
INK, MUTED, BLUE, RED, GRID = "#1f2933", "#6b7785", "#3b6ea5", "#c0392b", "#e3e7ec"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})
O = "screenshots/figs/"
cat = pd.read_csv("results/hive/hive_Q2.csv").sort_values("fraud_pct")
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.barh(cat.merchant_category, cat.fraud_pct, color=BLUE, height=.62)
ax.axvline(0.529, color=RED, lw=1.5, ls="--"); ax.text(0.54, 0.3, "overall 0.53%", color=RED, fontsize=9)
for y, v in enumerate(cat.fraud_pct): ax.text(v + .02, y, f"{v:.2f}%", va="center", fontsize=8, color=INK)
ax.set_xlabel("Fraud rate (% of transactions)"); ax.set_title("Fraud rate by merchant category", loc="left", color=INK, fontsize=12)
ax.grid(axis="x", color=GRID); ax.set_axisbelow(True); plt.tight_layout(); plt.savefig(O + "category.png", dpi=170); plt.close()

h = pd.read_csv("results/hive/hive_Q4.csv")
fig, ax = plt.subplots(figsize=(7, 3.6))
ax.plot(h.txn_hour, h.fraud_pct, color=BLUE, lw=2, marker="o", ms=4)
ax.axhline(0.529, color=RED, lw=1.2, ls="--"); ax.text(12, 0.56, "overall 0.53%", color=RED, fontsize=9)
ax.set_xticks(range(0, 24, 2)); ax.set_xlabel("Hour of day"); ax.set_ylabel("Fraud rate (%)")
ax.set_title("Fraud rate by hour: night-time (23:00-04:59) is more than twice the daytime rate", loc="left", color=INK, fontsize=11)
ax.grid(color=GRID); ax.set_axisbelow(True); ax.set_ylim(0, 1.4); plt.tight_layout(); plt.savefig(O + "hour.png", dpi=170); plt.close()

c = pd.read_csv("results/hive/hive_Q3.csv"); c["label"] = c.channel + (c.card_present.map({0: " (card not present)", 1: " (card present)"}))
c = c.sort_values("fraud_pct")
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.barh(c.label, c.fraud_pct, color=[RED if "not" in l else BLUE for l in c.label], height=.55)
for y, v in enumerate(c.fraud_pct): ax.text(v + .02, y, f"{v:.2f}%", va="center", fontsize=9, color=INK)
ax.set_xlabel("Fraud rate (%)"); ax.set_title("Card-not-present online carries the highest fraud rate", loc="left", color=INK, fontsize=11)
ax.grid(axis="x", color=GRID); ax.set_axisbelow(True); plt.tight_layout(); plt.savefig(O + "channel.png", dpi=170); plt.close()

d = json.load(open("results/pipeline_metrics.json"))["results"]
names = ["Logistic\nRegression", "Random\nForest", "Gradient\nBoosted Trees"]
r1 = [m["top1pct"]["recall_pct"] for m in d]; r5 = [m["top5pct"]["recall_pct"] for m in d]
fig, ax = plt.subplots(figsize=(7, 3.8)); x = range(3); w = .36
b1 = ax.bar([i - w/2 for i in x], r1, w, color=BLUE, label="Review top 1% riskiest"); b5 = ax.bar([i + w/2 for i in x], r5, w, color="#8fb3d9", label="Review top 5% riskiest")
for b in list(b1) + list(b5): ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f"{b.get_height():.1f}%", ha="center", fontsize=9, color=INK)
ax.set_xticks(list(x)); ax.set_xticklabels(names); ax.set_ylabel("Share of fraud caught (recall, %)"); ax.set_ylim(0, 62)
ax.set_title("Fraud caught when only the riskiest transactions are reviewed (test set)", loc="left", color=INK, fontsize=11)
ax.legend(frameon=False, fontsize=9, loc="upper left"); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
plt.tight_layout(); plt.savefig(O + "models.png", dpi=170); plt.close()

# Architecture diagram
fig, ax = plt.subplots(figsize=(7.2, 6.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 12.8)
boxes = [("Transaction source data", "CSV: 1,000,000 card transactions", 11.2, "#eef2f7"),
         ("HDFS", "/data/fraud/raw  ->  /processed  ->  /results", 9.4, "#dbe7f5"),
         ("Hive", "fraud_analytics.transactions (external table) + SQL analysis", 7.6, "#dbe7f5"),
         ("Spark / PySpark on YARN", "clean -> transform -> join -> aggregate -> window -> ML", 5.8, "#dbe7f5"),
         ("HBase (optional)  /  Pig (optional)", "card risk-profile lookup  /  data-flow cross-check", 4.0, "#eef2f7"),
         ("Results + insights", "fraud patterns, model comparison, review-queue strategy", 2.2, "#f9e3e0"),
         ("GitHub + README + PPT", "reproducible repository and presentation", 0.5, "#eef2f7")]
for t, s, y, col in boxes:
    ax.add_patch(FancyBboxPatch((1, y), 8, 1.2, boxstyle="round,pad=0.02,rounding_size=0.15", fc=col, ec="#9db3cc", lw=1))
    ax.text(5, y + .8, t, ha="center", va="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(5, y + .35, s, ha="center", va="center", fontsize=8.5, color=MUTED)
for y in [11.2, 9.4, 7.6, 5.8, 4.0, 2.2]:
    ax.annotate("", xy=(5, y - .55), xytext=(5, y), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.3))
plt.tight_layout(); plt.savefig(O + "architecture.png", dpi=170); plt.close()
print("done")
