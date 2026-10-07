# Evidence screenshots (add your own)

Save as PNG with these names. `figs/` holds generated charts used in the report.

| File | What to capture |
|---|---|
| 01_hdfs_ls.png | `hdfs dfs -ls -h /data/fraud/raw/` |
| 02_hdfs_fsck.png | `hdfs fsck ... -files -blocks -locations` |
| 03_namenode_ui.png | NameNode file browser |
| 04_hive_describe.png | `DESCRIBE FORMATTED transactions;` in Beeline |
| 05_hive_queries.png | Q1 to Q3 outputs |
| 06_spark_run.png | spark-submit or notebook output |
| 07_spark_ui.png | Spark master / application page |
| 08_yarn_ui.png | ResourceManager application |
| 09_hdfs_results.png | `hdfs dfs -ls -R /data/fraud/results` |
| 10_hbase.png | HBase get / scan |
| 11_pig.png | Pig DUMP matching Hive Q3 |
