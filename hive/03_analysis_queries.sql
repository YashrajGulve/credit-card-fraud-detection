USE fraud_analytics;

-- Q1 Overall fraud rate
SELECT COUNT(*) AS total_txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct,
       ROUND(SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END), 2) AS fraud_amount,
       ROUND(AVG(amount), 2) AS avg_amount
FROM transactions;

-- Q2 Fraud by merchant category
SELECT merchant_category,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct,
       ROUND(SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END), 2) AS fraud_amount
FROM transactions
GROUP BY merchant_category
ORDER BY fraud_pct DESC;

-- Q3 Fraud by channel and card presence
SELECT channel, card_present,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct
FROM transactions
GROUP BY channel, card_present
ORDER BY fraud_pct DESC;

-- Q4 Fraud by hour of day
SELECT hour(transaction_ts) AS txn_hour,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct
FROM transactions
GROUP BY hour(transaction_ts)
ORDER BY txn_hour;

-- Q5 Fraud by amount band
SELECT CASE WHEN amount < 500 THEN '1. <500'
            WHEN amount < 2000 THEN '2. 500-1999'
            WHEN amount < 5000 THEN '3. 2000-4999'
            WHEN amount < 10000 THEN '4. 5000-9999'
            ELSE '5. 10000+' END AS amount_band,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct
FROM transactions
GROUP BY CASE WHEN amount < 500 THEN '1. <500'
              WHEN amount < 2000 THEN '2. 500-1999'
              WHEN amount < 5000 THEN '3. 2000-4999'
              WHEN amount < 10000 THEN '4. 5000-9999'
              ELSE '5. 10000+' END
ORDER BY amount_band;

-- Q6 Monthly trend
SELECT month(transaction_ts) AS txn_month,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct
FROM transactions
GROUP BY month(transaction_ts)
ORDER BY txn_month;

-- Q7 International and velocity risk signals
SELECT is_international,
       CASE WHEN txn_count_24h >= 5 THEN 'HIGH_VELOCITY' ELSE 'NORMAL' END AS velocity_flag,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct
FROM transactions
GROUP BY is_international,
         CASE WHEN txn_count_24h >= 5 THEN 'HIGH_VELOCITY' ELSE 'NORMAL' END
ORDER BY fraud_pct DESC;

-- Q8 Top 10 riskiest merchants (minimum 150 transactions)
SELECT merchant_id,
       COUNT(*) AS txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 3) AS fraud_pct
FROM transactions
GROUP BY merchant_id
HAVING COUNT(*) >= 150
ORDER BY fraud_pct DESC, fraud_txns DESC
LIMIT 10;
