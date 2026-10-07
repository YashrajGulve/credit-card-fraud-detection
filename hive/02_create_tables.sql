USE fraud_analytics;

-- Raw external table: data stays in HDFS, Hive only stores metadata.
-- DROP TABLE will NOT delete /data/fraud/raw/transactions.csv
CREATE EXTERNAL TABLE IF NOT EXISTS transactions (
  transaction_id         STRING,
  transaction_ts         TIMESTAMP,
  card_id                STRING,
  customer_age           INT,
  customer_state         STRING,
  merchant_id            STRING,
  merchant_category      STRING,
  channel                STRING,
  amount                 DOUBLE,
  card_present           INT,
  distance_from_home_km  DOUBLE,
  txn_count_24h          INT,
  minutes_since_last_txn DOUBLE,
  is_international       INT,
  amount_vs_card_avg     DOUBLE,
  is_fraud               INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/data/fraud/raw/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- Optional extension: partitioned ORC table for faster monthly queries
SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;

CREATE TABLE IF NOT EXISTS transactions_orc (
  transaction_id STRING, transaction_ts TIMESTAMP, card_id STRING, customer_age INT,
  customer_state STRING, merchant_id STRING, merchant_category STRING, channel STRING,
  amount DOUBLE, card_present INT, distance_from_home_km DOUBLE, txn_count_24h INT,
  minutes_since_last_txn DOUBLE, is_international INT, amount_vs_card_avg DOUBLE, is_fraud INT
)
PARTITIONED BY (txn_month INT)
STORED AS ORC;

INSERT OVERWRITE TABLE transactions_orc PARTITION (txn_month)
SELECT t.*, month(transaction_ts) AS txn_month FROM transactions t;

SHOW PARTITIONS transactions_orc;
DESCRIBE FORMATTED transactions;
