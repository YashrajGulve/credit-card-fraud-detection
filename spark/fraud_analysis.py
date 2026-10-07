"""
Credit Card Fraud Detection - PySpark pipeline
Stages: read -> quality checks -> transformations -> aggregations/window analytics
        -> write results -> ML (Logistic Regression, Random Forest) -> evaluation

Usage (cluster):  spark-submit --master yarn fraud_analysis.py \
                      hdfs://namenode:8020/data/fraud/raw/transactions.csv \
                      hdfs://namenode:8020/data/fraud/results
Usage (local):    python fraud_analysis.py transactions.csv ./results/spark_out
"""
import os, sys, json, time
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.ml.classification import LogisticRegression, RandomForestClassifier, GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.functions import vector_to_array

src, out = sys.argv[1], sys.argv[2]
def _session(app):
    """Master is chosen by the launcher: spark-submit --master ..., or SPARK_MASTER env,
    or (plain `python`) local[2]. Nothing is hardcoded so --master yarn really is used."""
    b = SparkSession.builder.appName(app).config("spark.sql.shuffle.partitions", os.environ.get("SHUFFLE_PARTITIONS", "8"))
    if os.environ.get("SPARK_MASTER"):
        b = b.master(os.environ["SPARK_MASTER"])
    elif "PYSPARK_GATEWAY_PORT" not in os.environ:      # plain `python fraud_analysis.py`
        b = b.master("local[2]").config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "4g"))
    return b.getOrCreate()
spark = _session("CreditCardFraudAnalytics")
spark.sparkContext.setLogLevel("ERROR")
log, t0 = {}, time.time()
def tick(k): log.setdefault("timings_sec", {})[k] = round(time.time() - t0, 1)

# 1. READ -------------------------------------------------------------------
df = spark.read.option("header", True).option("inferSchema", True).csv(src)
df.printSchema()
n = df.count(); log["records"] = n; log["input_partitions"] = df.rdd.getNumPartitions()
tick("read_and_count")

# 2. DATA QUALITY -----------------------------------------------------------
nulls = df.select([F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in df.columns]).first().asDict()
log["quality"] = {
    "null_counts": nulls,
    "negative_or_zero_amount": df.filter(F.col("amount") <= 0).count(),
    "invalid_label": df.filter(~F.col("is_fraud").isin(0, 1)).count(),
    "duplicate_transaction_ids": n - df.select("transaction_id").distinct().count(),
}
print(json.dumps(log["quality"], indent=1)); tick("quality_checks")

# 3. TRANSFORMATIONS --------------------------------------------------------
df2 = (df.withColumn("transaction_ts", F.to_timestamp("transaction_ts"))
         .withColumn("txn_hour", F.hour("transaction_ts"))
         .withColumn("txn_month", F.month("transaction_ts"))
         .withColumn("txn_dow", F.dayofweek("transaction_ts"))
         .withColumn("txn_date", F.to_date("transaction_ts"))
         .withColumn("is_night", F.when((F.col("txn_hour") <= 4) | (F.col("txn_hour") == 23), 1).otherwise(0))
         .withColumn("high_velocity", F.when(F.col("txn_count_24h") >= 5, 1).otherwise(0))
         .withColumn("rapid_repeat", F.when(F.col("minutes_since_last_txn") < 5, 1).otherwise(0))
         .withColumn("log_amount", F.log1p("amount"))
         .withColumn("amount_band",
              F.when(F.col("amount") < 500, "1. <500").when(F.col("amount") < 2000, "2. 500-1999")
               .when(F.col("amount") < 5000, "3. 2000-4999").when(F.col("amount") < 10000, "4. 5000-9999")
               .otherwise("5. 10000+")))
df2 = df2.repartition(8, "txn_month").cache()      # reused many times below -> cache
df2.count(); log["cached_partitions"] = df2.rdd.getNumPartitions(); tick("transform_cache")

# 4. DISTRIBUTED AGGREGATIONS ----------------------------------------------
def rate(): return F.round(F.avg("is_fraud") * 100, 3).alias("fraud_pct")
agg = lambda g: (df2.groupBy(*g).agg(F.count("*").alias("txns"), F.sum("is_fraud").alias("fraud_txns"), rate(),
                 F.round(F.sum(F.when(F.col("is_fraud") == 1, F.col("amount")).otherwise(0)), 2).alias("fraud_amount")))
summaries = {
    "category_summary": agg(["merchant_category"]).orderBy(F.desc("fraud_pct")),
    "channel_summary": agg(["channel"]).orderBy(F.desc("fraud_pct")),
    "hour_summary": agg(["txn_hour"]).orderBy("txn_hour"),
    "state_summary": agg(["customer_state"]).orderBy(F.desc("fraud_pct")),
    "amount_band_summary": agg(["amount_band"]).orderBy("amount_band"),
    "month_summary": agg(["txn_month"]).orderBy("txn_month"),
}
age_df = df2.withColumn("age_group", F.when(F.col("customer_age") < 25, "18-24").when(F.col("customer_age") < 35, "25-34")
                         .when(F.col("customer_age") < 50, "35-49").when(F.col("customer_age") < 65, "50-64").otherwise("65+"))
summaries["age_summary"] = age_df.groupBy("age_group").agg(F.count("*").alias("txns"), F.sum("is_fraud").alias("fraud_txns"), rate()).orderBy("age_group")

# Card-level risk profile (used for HBase lookup) -----------------------------
card_profile = (df2.groupBy("card_id").agg(F.count("*").alias("txns"), F.sum("is_fraud").alias("fraud_txns"),
                 F.round(F.avg("amount"), 2).alias("avg_amount"), F.max("txn_count_24h").alias("max_txn_24h"))
                .withColumn("risk_flag", F.when(F.col("fraud_txns") >= 2, "HIGH").when(F.col("fraud_txns") == 1, "MEDIUM").otherwise("LOW")))
summaries["card_risk_profile"] = card_profile
log["card_risk_distribution"] = {r["risk_flag"]: r["count"] for r in card_profile.groupBy("risk_flag").count().collect()}
log["distinct_cards"] = card_profile.count()

# Window analytics 1: rank categories inside each channel by fraud rate
cc = df2.groupBy("channel", "merchant_category").agg(F.count("*").alias("txns"), rate())
w = Window.partitionBy("channel").orderBy(F.desc("fraud_pct"))
summaries["channel_category_rank"] = cc.withColumn("rank_in_channel", F.row_number().over(w)).filter("rank_in_channel <= 3").orderBy("channel", "rank_in_channel")

# Window analytics 2: 7-day moving average of daily fraud count
daily = df2.groupBy("txn_date").agg(F.count("*").alias("txns"), F.sum("is_fraud").alias("fraud_txns"))
w7 = Window.orderBy(F.col("txn_date").cast("timestamp").cast("long")).rangeBetween(-6 * 86400, 0)
summaries["daily_trend"] = daily.withColumn("fraud_7d_avg", F.round(F.avg("fraud_txns").over(w7), 2)).orderBy("txn_date")

# Join: enrich with a state->region lookup table (broadcast join)
region = spark.createDataFrame([("MH","West"),("GJ","West"),("RJ","West"),("KA","South"),("TN","South"),("TG","South"),
                                ("KL","South"),("DL","North"),("UP","North"),("WB","East")], ["customer_state", "region"])
summaries["region_summary"] = (df2.join(F.broadcast(region), "customer_state", "left").groupBy("region")
        .agg(F.count("*").alias("txns"), F.sum("is_fraud").alias("fraud_txns"), rate()).orderBy(F.desc("fraud_pct")))

for name, sdf in summaries.items():
    sdf.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{out}/{name}")
tick("aggregations_and_write")

# Processed (columnar, partitioned) copy of the data for downstream use
processed_path = out.rstrip("/").rsplit("/", 1)[0] + "/processed"      # sibling of results/, e.g. /data/fraud/processed
df2.drop("log_amount").write.mode("overwrite").partitionBy("txn_month").parquet(processed_path)
tick("parquet_write")

# 5. MACHINE LEARNING -------------------------------------------------------
# Time-based split: train Jan-Sep, test Oct-Dec (no leakage from the future)
train = df2.filter("txn_month <= 9"); test = df2.filter("txn_month >= 10")
n_tr, n_te = train.count(), test.count()
fr_tr = train.agg(F.avg("is_fraud")).first()[0]
log["split"] = {"train_rows": n_tr, "test_rows": n_te, "train_fraud_pct": round(fr_tr*100,3),
                "test_fraud_pct": round(test.agg(F.avg("is_fraud")).first()[0]*100,3)}
# class weight to handle imbalance
wpos = (1 - fr_tr) / fr_tr
train = train.withColumn("w", F.when(F.col("is_fraud") == 1, F.lit(wpos)).otherwise(F.lit(1.0)))

cat_cols = ["merchant_category", "channel"]
num_cols = ["log_amount", "card_present", "distance_from_home_km", "txn_count_24h", "minutes_since_last_txn",
            "is_international", "amount_vs_card_avg", "is_night", "rapid_repeat", "high_velocity", "customer_age"]
idx = [StringIndexer(inputCol=c, outputCol=c + "_i", handleInvalid="keep") for c in cat_cols]
ohe = OneHotEncoder(inputCols=[c + "_i" for c in cat_cols], outputCols=[c + "_v" for c in cat_cols])
asm = VectorAssembler(inputCols=num_cols + [c + "_v" for c in cat_cols], outputCol="features")
feature_names = None

def evaluate(model_name, pipe_model, extra=None):
    pred = pipe_model.transform(test).withColumn("p", vector_to_array("probability")[1]).select("is_fraud", "p", "amount").cache()
    roc = BinaryClassificationEvaluator(labelCol="is_fraud", rawPredictionCol="rawPrediction", metricName="areaUnderROC").evaluate(pipe_model.transform(test))
    pr = BinaryClassificationEvaluator(labelCol="is_fraud", rawPredictionCol="rawPrediction", metricName="areaUnderPR").evaluate(pipe_model.transform(test))
    tot_f = pred.agg(F.sum("is_fraud")).first()[0]
    # operating point: flag the top 1% and top 5% highest-risk transactions
    res = {"model": model_name, "auc_roc": round(roc, 4), "auc_pr": round(pr, 4)}
    for pct in (0.01, 0.05):
        thr = pred.approxQuantile("p", [1 - pct], 0.0005)[0]
        fl = pred.filter(F.col("p") >= thr)
        tp = fl.agg(F.sum("is_fraud")).first()[0]; flagged = fl.count()
        res[f"top{int(pct*100)}pct"] = {"flagged": flagged, "caught_fraud": int(tp),
              "recall_pct": round(100 * tp / tot_f, 2), "precision_pct": round(100 * tp / flagged, 2),
              "lift": round((tp / flagged) / (tot_f / n_te), 1),
              "fraud_amount_caught_pct": round(100 * fl.filter("is_fraud=1").agg(F.sum("amount")).first()[0] / pred.filter("is_fraud=1").agg(F.sum("amount")).first()[0], 2)}
    # confusion matrix at the top-1% threshold
    thr1 = pred.approxQuantile("p", [0.99], 0.0005)[0]
    cm = pred.withColumn("yhat", (F.col("p") >= thr1).cast("int")).groupBy("is_fraud", "yhat").count().collect()
    res["confusion_top1pct"] = {f"actual{r['is_fraud']}_pred{r['yhat']}": r["count"] for r in cm}
    if extra: res.update(extra)
    pred.unpersist(); return res

models = {}
lr = LogisticRegression(featuresCol="features", labelCol="is_fraud", weightCol="w", maxIter=40, regParam=0.001)
m_lr = Pipeline(stages=idx + [ohe, asm, lr]).fit(train); tick("train_logreg")
rf = RandomForestClassifier(featuresCol="features", labelCol="is_fraud", weightCol="w", numTrees=60, maxDepth=8, seed=7)
m_rf = Pipeline(stages=idx + [ohe, asm, rf]).fit(train); tick("train_random_forest")
gbt = GBTClassifier(featuresCol="features", labelCol="is_fraud", weightCol="w", maxIter=40, maxDepth=4, stepSize=0.1, seed=7)
m_gbt = Pipeline(stages=idx + [ohe, asm, gbt]).fit(train); tick("train_gbt")

imp = m_rf.stages[-1].featureImportances.toArray()
names = list(num_cols)              # copy - OHE vectors drop the last category (dropLast=True)
for i, c in enumerate(cat_cols):
    labs = m_rf.stages[i].labels; names += [f"{c}={l}" for l in labs[:len(labs) - 1]]
imp_list = sorted(zip(names, imp), key=lambda x: -x[1])[:12]
coef = m_lr.stages[-1].coefficients.toArray()
coef_list = sorted([(n_, float(c_)) for n_, c_ in zip(names, coef)], key=lambda x: -abs(x[1]))[:12]

log["results"] = [evaluate("Logistic Regression", m_lr), evaluate("Random Forest", m_rf), evaluate("Gradient Boosted Trees", m_gbt)]
log["rf_feature_importance"] = [(a, round(float(b), 4)) for a, b in imp_list]
gimp = sorted(zip(names, m_gbt.stages[-1].featureImportances.toArray()), key=lambda x: -x[1])[:12]
log["gbt_feature_importance"] = [(a, round(float(b), 4)) for a, b in gimp]
log["lr_numeric_coefficients"] = [(a, round(b, 3)) for a, b in coef_list]
tick("evaluate")

# 6. SAVE LOG ---------------------------------------------------------------
payload = json.dumps(log, indent=1, default=str)
if "://" in out:                                   # HDFS (or other Hadoop FS): save through Spark, never open()
    spark.sparkContext.parallelize([payload], 1).saveAsTextFile(out.rstrip("/") + "/pipeline_metrics")
    with open("pipeline_metrics.json", "w") as f: f.write(payload)   # local copy in the working directory
else:                                              # local run: results/pipeline_metrics.json next to spark_out/
    local_dir = os.path.dirname(out.rstrip("/")) or "."
    os.makedirs(local_dir, exist_ok=True)
    with open(os.path.join(local_dir, "pipeline_metrics.json"), "w") as f: f.write(payload)
print(payload)
spark.stop()
