# Dataset

`transactions.csv` is **synthetic**: 1,000,000 card transactions over 12 months (2025), 16 columns, about 93 MB.
It is not committed (GitHub warns above 50 MB). Generate it, reproducibly (seed 42):

    python data/generate_dataset.py --rows 1000000 --out data/transactions.csv

`sample/transactions_sample_4000.csv` is the first 4,000 rows for quick tests.

Why synthetic: real card data is confidential, and public sets (for example Kaggle ULB `creditcard.csv`) have anonymised PCA columns that make business questions hard to ask.
Fraud patterns (night hours, card-not-present, high-risk categories, large amounts, distance, international use, velocity) are built into the generator, so findings demonstrate the pipeline and are not evidence about real fraud.
Fraud rate is 0.529% (5,290 of 1,000,000).

## Data dictionary

| Column | Type | Example | Meaning |
|---|---|---|---|
| transaction_id | STRING | T10390367 | Unique transaction identifier |
| transaction_ts | TIMESTAMP | 2025-01-01 00:04:43 | Date and time |
| card_id | STRING | C166916 | Card identifier |
| customer_age | INT | 57 | Cardholder age |
| customer_state | STRING | DL | Home state |
| merchant_id | STRING | M1293 | Merchant identifier |
| merchant_category | STRING | Utilities | One of 12 categories |
| channel | STRING | Contactless | POS, Contactless, ATM, Online |
| amount | DOUBLE | 321.64 | Amount in rupees |
| card_present | INT | 1 | 1 = physical card, 0 = card-not-present |
| distance_from_home_km | DOUBLE | 15.9 | Distance from cardholder's home |
| txn_count_24h | INT | 2 | Transactions on the card in last 24 hours |
| minutes_since_last_txn | DOUBLE | 606.2 | Minutes since previous transaction on the card |
| is_international | INT | 0 | 1 = outside home country |
| amount_vs_card_avg | DOUBLE | 1.25 | Amount divided by the card's usual average |
| is_fraud | INT | 0 | Label: 1 = fraud |
