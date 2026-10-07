-- Pig data-flow cross-check: fraud count and amount by channel.
-- Result should match Hive Query Q3 / Spark channel_summary.
txns = LOAD '/data/fraud/raw/transactions.csv' USING PigStorage(',')
       AS (transaction_id:chararray, transaction_ts:chararray, card_id:chararray, customer_age:int,
           customer_state:chararray, merchant_id:chararray, merchant_category:chararray, channel:chararray,
           amount:double, card_present:int, distance_from_home_km:double, txn_count_24h:int,
           minutes_since_last_txn:double, is_international:int, amount_vs_card_avg:double, is_fraud:int);
data    = FILTER txns BY transaction_id != 'transaction_id';      -- drop header row
by_chan = GROUP data BY channel;
summary = FOREACH by_chan {
            fraud = FILTER data BY is_fraud == 1;
            GENERATE group AS channel, COUNT(data) AS txns, COUNT(fraud) AS fraud_txns,
                     SUM(fraud.amount) AS fraud_amount;
          };
ordered = ORDER summary BY fraud_txns DESC;
DUMP ordered;
STORE ordered INTO '/data/fraud/results/pig_channel_summary' USING PigStorage(',');
