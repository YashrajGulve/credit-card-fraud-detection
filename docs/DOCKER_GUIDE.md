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

## Quick path with the supplied `docker-compose.full.yml`

`docker-compose.full.yml` (repo root, supplied by the course, unmodified) starts a Spark master and one worker (Spark 3.5.7) on the existing network `big_data_pj_default`.
It does **not** include HDFS, Hive, YARN or Jupyter. HDFS, Hive and YARN come from the course's core compose file, which must be started first because it creates that network. There is no Jupyter service in this file, so `localhost:8888` is not available from it.

Because the file sits in the repo root, its mounts line up with the project folders: `./spark` appears in the containers as `/workspace/spark` and `./results` as `/workspace/results`. Spark output written under `/workspace/results` therefore lands in this repo's `results/` folder.

    docker network ls | findstr big_data_pj                      # network must exist (start the core stack first)
    docker compose -f docker-compose.full.yml up -d
    docker exec spark-master which python3                       # must print a path, otherwise PySpark cannot run

Web pages: Spark master http://localhost:8080, worker http://localhost:8081.

Copy `transactions.csv` (generate it with `data/generate_dataset.py`) into the `spark` folder, then:

    docker exec -it spark-master /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
        /workspace/spark/hdfs_connect.py --local-csv /workspace/spark/transactions.csv --run-analysis

`hdfs_connect.py` defaults to `hdfs://namenode:8020`. If the core file uses another service name or port, pass `--hdfs-uri`. Do not commit `spark/transactions.csv` (it is large).
The sections below describe the same steps in general form; where they use `docker cp`, the mounted folders above replace it.

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

## 3b. One-script option: `spark/hdfs_connect.py`

Connects to the NameNode, creates `/data/fraud/{raw,processed,results}`, uploads the CSV, lists and reads it back, and optionally runs the whole analysis on the HDFS data.
Run it inside a container on the compose network so the name `namenode` resolves:

    docker cp spark/. spark-master:/opt/fraud/
    docker cp data/transactions.csv spark-master:/tmp/transactions.csv
    docker exec -it spark-master spark-submit --master spark://spark-master:7077 \
        /opt/fraud/hdfs_connect.py --local-csv /tmp/transactions.csv --run-analysis

    # connection test only
    docker exec -it spark-master spark-submit /opt/fraud/hdfs_connect.py --check-only

Flags: `--hdfs-uri` (default `hdfs://namenode:8020`), `--base` (default `/data/fraud`), `--master` (`yarn` or `spark://spark-master:7077`), `--overwrite`.
If PySpark reports a missing `numpy` on the executors, run `pip install numpy` inside the Spark containers.
The script was tested end to end against a local `file://` filesystem in place of HDFS; it has not been run against your containers.

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
