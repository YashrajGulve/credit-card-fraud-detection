"""
Generate a synthetic credit-card transaction dataset for the Big Data capstone.

Why synthetic: real card data is confidential and public sets (e.g. Kaggle ULB
creditcard.csv) have anonymised PCA columns that make business questions hard to
ask. This generator creates business-readable columns with realistic fraud
patterns. Replace with your own real dataset if your trainer requires it.

Usage:  python generate_dataset.py --rows 1000000 --out transactions.csv
"""
import argparse
import numpy as np
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--rows", type=int, default=1_000_000)
p.add_argument("--out", default="transactions.csv")
p.add_argument("--seed", type=int, default=42)
a = p.parse_args()
rng = np.random.default_rng(a.seed)
n = a.rows

# ---- categorical domains -------------------------------------------------
cats = ["Grocery", "Fuel", "Restaurant", "Utilities", "Healthcare", "Apparel",
        "Travel", "Electronics", "Jewelry", "Gift Cards", "Entertainment", "Online Services"]
cat_p = np.array([.20, .12, .15, .08, .06, .09, .05, .06, .02, .02, .08, .07])
cat_risk = {"Grocery": -0.6, "Fuel": -0.2, "Restaurant": -0.4, "Utilities": -0.8, "Healthcare": -0.7,
            "Apparel": 0.0, "Travel": 0.5, "Electronics": 0.9, "Jewelry": 1.2, "Gift Cards": 1.5,
            "Entertainment": 0.1, "Online Services": 0.4}
channels = ["POS", "Online", "ATM", "Contactless"]
chan_p = np.array([.38, .30, .07, .25])
states = ["MH", "KA", "DL", "TN", "TG", "GJ", "WB", "UP", "RJ", "KL"]

# ---- base features -------------------------------------------------------
n_cards = max(n // 12, 1000)
card_idx = rng.integers(0, n_cards, n)
card_id = np.char.add("C", (100000 + card_idx).astype(str))
merchant_id = np.char.add("M", rng.integers(1000, 6000, n).astype(str))
category = rng.choice(cats, n, p=cat_p)
channel = rng.choice(channels, n, p=chan_p)
state = rng.choice(states, n)
age = np.clip(rng.normal(41, 13, n), 18, 85).astype(int)

# timestamps over 12 months of 2025, hour-of-day shaped
day = rng.integers(0, 365, n)
hour_p = np.array([1,1,1,1,1,2,3,5,6,6,6,7,7,6,6,6,6,7,7,7,6,5,3,2], float)
hour = rng.choice(24, n, p=hour_p / hour_p.sum())
minute = rng.integers(0, 60, n); sec = rng.integers(0, 60, n)
ts = (pd.Timestamp("2025-01-01") + pd.to_timedelta(day, "D") + pd.to_timedelta(hour, "h")
      + pd.to_timedelta(minute, "m") + pd.to_timedelta(sec, "s"))

amount = np.round(np.exp(rng.normal(6.6, 1.0, n)), 2)          # median about Rs 735
amount = np.where(channel == "ATM", np.round(rng.choice([1000, 2000, 5000, 10000, 20000], n), 2), amount)
amount = np.where(np.isin(category, ["Electronics", "Jewelry", "Travel"]), amount * 2.2, amount).round(2)

card_present = np.isin(channel, ["POS", "Contactless", "ATM"]).astype(int)
dist = np.where(card_present == 1, rng.gamma(1.4, 6, n), rng.gamma(1.6, 40, n)).round(1)
txn_count_24h = rng.poisson(1.6, n) + 1
gap = np.round(rng.exponential(600, n) + 1, 1)                   # minutes since previous txn on card
is_international = (rng.random(n) < np.where(channel == "Online", .08, .015)).astype(int)
avg_ticket_ratio = np.round(np.exp(rng.normal(0, .55, n)), 2)    # amount / card's usual avg

# ---- fraud label from a noisy logistic model -----------------------------
night = ((hour <= 4) | (hour == 23)).astype(int)
z = (-8.3
     + 0.9 * (channel == "Online") + 0.5 * (channel == "ATM")
     + np.array([cat_risk[c] for c in category])
     + 0.9 * night
     + 1.3 * np.log1p(np.maximum(avg_ticket_ratio - 1, 0) * 2)
     + 0.45 * np.log1p(amount / 1000)
     + 0.012 * np.minimum(dist, 250)
     + 1.4 * is_international
     + 0.55 * np.maximum(txn_count_24h - 3, 0)
     + 1.1 * (gap < 5)
     + rng.normal(0, .9, n))
prob = 1 / (1 + np.exp(-z))
is_fraud = (rng.random(n) < prob).astype(int)

df = pd.DataFrame({
    "transaction_id": np.char.add("T", (10_000_000 + np.arange(n)).astype(str)),
    "transaction_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
    "card_id": card_id, "customer_age": age, "customer_state": state,
    "merchant_id": merchant_id, "merchant_category": category, "channel": channel,
    "amount": amount, "card_present": card_present, "distance_from_home_km": dist,
    "txn_count_24h": txn_count_24h, "minutes_since_last_txn": gap,
    "is_international": is_international, "amount_vs_card_avg": avg_ticket_ratio,
    "is_fraud": is_fraud,
}).sort_values("transaction_ts")
df.to_csv(a.out, index=False)
print(f"rows={len(df):,} fraud={df.is_fraud.sum():,} ({100*df.is_fraud.mean():.2f}%) -> {a.out}")
