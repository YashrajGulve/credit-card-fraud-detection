# Running the project in the course Docker environment

The course supplies a `docker-compose.yml` that starts Hadoop, Hive, Spark, HBase, Pig and Jupyter as containers on a shared network. **Do not edit it unless your trainer asks.**
Container names, profiles and ports below are common defaults. Confirm yours with `docker ps` and your compose file.

| Container | Tool | Typical UI port |
|---|---|---|
| namenode, datanode | HDFS | 9870, 9864 |
| resourcemanager, nodemanager | YARN | 8088 |
| hive-metastore, hiveserver2 | Hive | 10000 |
| spark-master, spark-worker | Spark | 8080 |
| jupyter | PySpark notebook | 8888 |
| hbase, pig | HBase, Pig | 16010 |

## 1. Start and check

    docker compose --profile full up -d     # profile flag as given by your trainer
    docker ps

## 2. Data into HDFS

    python data/generate_dataset.py --rows 1000000 --out data/transactions.csv
    docker cp data/transactions.csv namenode:/tmp/
    docker exec -it namenode bash
    # then run the commands in hdfs/hdfs_commands.txt

## 3. Hive

    docker cp hive/. hiveserver2:/tmp/hive/
    docker exec -it hiveserver2 beeline -u jdbc:hive2://localhost:10000 -f /tmp/hive/02_create_tables.sql
    docker exec -it hiveserver2 beeline -u jdbc:hive2://localhost:10000 -f /tmp/hive/03_analysis_queries.sql

Compare with `results/hive/hive_Q1.csv` to `hive_Q8.csv`; they should match.

## 4. Spark

    docker cp spark/fraud_analysis.py spark-master:/tmp/
    docker exec -it spark-master spark-submit --master yarn /tmp/fraud_analysis.py \
      hdfs://namenode:8020/data/fraud/raw/transactions.csv \
      hdfs://namenode:8020/data/fraud/results

## 5. HBase and Pig

Run `hbase/hbase_commands.txt` in `hbase shell` and `pig/fraud_analysis.pig` in Pig. Pig output should match Hive Q3.

## Troubleshooting

| Symptom | First check |
|---|---|
| A service is not Up | `docker ps -a`, then `docker logs <container>` |
| `hdfs dfs` fails | NameNode up? `hdfs dfsadmin -report` shows live DataNodes |
| Hive table returns nothing | `DESCRIBE FORMATTED transactions;` check LOCATION, and that the file is in `/data/fraud/raw/` |
| Spark cannot read the path | Use the `hdfs://namenode:8020/...` URI, not a local path |
| Spark job stuck in ACCEPTED | YARN UI at :8088 for available memory |

Evidence to capture for evaluation is listed in `screenshots/README.md`.
