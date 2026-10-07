# Results

Produced by running the scripts on all 1,000,000 rows in Spark local mode (2 cores).

| Path | Content | Produced by |
|---|---|---|
| hive/hive_Q1..Q8.csv | Output of `hive/03_analysis_queries.sql` | `spark/run_sql_queries.py` (Spark SQL; compare with your Beeline output) |
| hive_queries_output.txt | Console output of the same run | same |
| spark_out/*/part-*.csv | 11 summary tables | `spark/fraud_analysis.py` |
| pipeline_metrics.json | Quality checks, timings, model metrics, feature importance | same |

The partitioned Parquet output (`processed_parquet/`) is ignored by git; the pipeline recreates it.

Headline numbers: fraud 5,290 (0.529%); Gift Cards 2.03%; online card-not-present 1.22%; night hours 2.4x daytime; best model logistic regression AUC-ROC 0.861, reviewing the top 1% catches 23.6% of fraud.
