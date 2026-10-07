"""Runs hive/03_analysis_queries.sql on the full dataset using Spark SQL.
Same HiveQL-compatible statements; table `transactions` is exposed as a temp view.
Usage: spark-submit run_sql_queries.py <input_csv_or_hdfs_path> <out_dir>"""
import sys, re, json, os
from pyspark.sql import SparkSession
src, out = sys.argv[1], sys.argv[2]
_b = SparkSession.builder.appName("FraudHiveQueries").config("spark.sql.shuffle.partitions", "8")
if os.environ.get("SPARK_MASTER"): _b = _b.master(os.environ["SPARK_MASTER"])
elif "PYSPARK_GATEWAY_PORT" not in os.environ: _b = _b.master("local[2]").config("spark.driver.memory", "4g")
spark = _b.getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
df = spark.read.option("header", True).option("inferSchema", True).csv(src)
df.createOrReplaceTempView("transactions")
sql_text = open(os.path.join(os.path.dirname(__file__), "..", "hive", "03_analysis_queries.sql")).read()
blocks = re.split(r"-- (Q\d+)[^\n]*\n", sql_text)[1:]
os.makedirs(out, exist_ok=True)
for name, body in zip(blocks[0::2], blocks[1::2]):
    q = body.replace("USE fraud_analytics;", "").strip().rstrip(";")
    pdf = spark.sql(q).toPandas()
    pdf.to_csv(f"{out}/hive_{name}.csv", index=False)
    print(f"\n=== {name} ===\n{pdf.to_string(index=False)}")
