"""
HDFS connector for the Credit Card Fraud project (runs inside the Docker Compose network).

What it does
  1. connects to HDFS and prints the namespace root          (proves the container can reach the NameNode)
  2. creates /data/fraud/{raw,processed,results}
  3. uploads a local CSV to /data/fraud/raw/                  (same as `hdfs dfs -put`)
  4. lists and measures the files, reads 5 rows back          (same as `hdfs dfs -ls / -du / -cat | head`)
  5. optionally runs the full analysis (fraud_analysis.py) reading from and writing to HDFS

Run it inside a container that is on the same Docker network as the NameNode
(spark-master, jupyter, or any Spark container), so the host name `namenode` resolves.

    docker cp spark/. spark-master:/opt/fraud/
    docker cp transactions.csv spark-master:/tmp/transactions.csv
    docker exec -it spark-master spark-submit --master spark://spark-master:7077 \
        /opt/fraud/hdfs_connect.py --local-csv /tmp/transactions.csv --run-analysis

    # connectivity test only:
    docker exec -it spark-master spark-submit /opt/fraud/hdfs_connect.py --check-only

Settings (flag or environment variable):
    --hdfs-uri      HDFS_URI       default hdfs://namenode:8020
    --base          HDFS_BASE      default /data/fraud
    --master        SPARK_MASTER   default: whatever spark-submit gives, else local[2]
Use --master yarn for YARN, or spark://spark-master:7077 for the standalone Spark master.
Check your own compose file for the real host names and ports.
"""
import argparse, os, runpy, sys
from pyspark.sql import SparkSession

ap = argparse.ArgumentParser()
ap.add_argument("--hdfs-uri", default=os.environ.get("HDFS_URI", "hdfs://namenode:8020"))
ap.add_argument("--base", default=os.environ.get("HDFS_BASE", "/data/fraud"))
ap.add_argument("--master", default=os.environ.get("SPARK_MASTER"))
ap.add_argument("--local-csv", help="local CSV to upload to <base>/raw/")
ap.add_argument("--overwrite", action="store_true", help="replace the HDFS file if it already exists")
ap.add_argument("--check-only", action="store_true", help="only test the HDFS connection and list the folders")
ap.add_argument("--run-analysis", action="store_true", help="run fraud_analysis.py on the HDFS data afterwards")
a = ap.parse_args()

b = SparkSession.builder.appName("FraudHDFSConnect")
if a.master: b = b.master(a.master)
elif "PYSPARK_GATEWAY_PORT" not in os.environ: b = b.master("local[2]").config("spark.driver.memory", "4g")
b = b.config("spark.hadoop.fs.defaultFS", a.hdfs_uri)
spark = b.getOrCreate(); spark.sparkContext.setLogLevel("ERROR")

jvm = spark._jvm; conf = spark._jsc.hadoopConfiguration()
Path = jvm.org.apache.hadoop.fs.Path
fs = jvm.org.apache.hadoop.fs.FileSystem.get(jvm.java.net.URI(a.hdfs_uri), conf)
P = lambda p: Path(a.hdfs_uri.rstrip("/") + p)

def ls(path):
    out = []
    if not fs.exists(P(path)): return out
    for st in fs.listStatus(P(path)):
        out.append((st.getPath().toString(), st.getLen(), st.isDirectory(), st.getReplication(), st.getBlockSize()))
    return out

# 1. connect --------------------------------------------------------------
print(f"\n[1] Connected to {a.hdfs_uri}  (Spark master: {spark.sparkContext.master})")
for name, size, is_dir, rep, blk in ls("/"):
    print("    " + ("dir  " if is_dir else "file ") + name)

# 2. directories ----------------------------------------------------------
raw, processed, results = f"{a.base}/raw", f"{a.base}/processed", f"{a.base}/results"
if not a.check_only:
    for d in (raw, processed, results):
        print(f"[2] mkdirs {d}: {fs.mkdirs(P(d))}")

# 3. upload ---------------------------------------------------------------
target = f"{raw}/transactions.csv"
if a.local_csv:
    if not os.path.isfile(a.local_csv): sys.exit(f"ERROR: local file not found: {a.local_csv}")
    if fs.exists(P(target)) and not a.overwrite:
        print(f"[3] {target} already exists, skipping upload (use --overwrite to replace)")
    else:
        fs.copyFromLocalFile(False, True, Path("file://" + os.path.abspath(a.local_csv)), P(target))
        print(f"[3] uploaded {a.local_csv} -> {a.hdfs_uri}{target}")

# 4. verify ---------------------------------------------------------------
print(f"[4] contents of {a.base}")
for d in (raw, processed, results):
    items = ls(d)
    print(f"    {d}/  ({len(items)} item(s))")
    for name, size, is_dir, rep, blk in items:
        print(f"      {'dir ' if is_dir else 'file'} {name.rsplit('/',1)[-1]:<28} {size/1024/1024:8.1f} MB  replication={rep}  blocksize={blk//1024//1024} MB")
if fs.exists(P(target)):
    df = spark.read.option("header", True).csv(a.hdfs_uri + target)
    print(f"    read back from HDFS: {df.count():,} rows, {len(df.columns)} columns")
    df.show(5, truncate=False)
elif not a.check_only:
    print(f"    NOTE: {target} not found. Pass --local-csv to upload it.")

# 5. analysis -------------------------------------------------------------
if a.run_analysis:
    if not fs.exists(P(target)): sys.exit("ERROR: no data in HDFS to analyse")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraud_analysis.py")
    print(f"[5] running {script} on HDFS data")
    sys.argv = [script, a.hdfs_uri + target, a.hdfs_uri + results]
    runpy.run_path(script, run_name="__main__")        # reuses this Spark session; results go to HDFS
    spark = None
else:
    spark.stop()
