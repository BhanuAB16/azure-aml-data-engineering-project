# Databricks notebook source
# MAGIC %md
# MAGIC # Silver -> Gold: feature engineering for AML detection
# MAGIC Builds per-account and per-transaction features (velocity, fan-in/out,
# MAGIC cross-currency flags) used for both the ML model and BI dashboards.

# COMMAND ----------

dbutils.widgets.text("storage_account", "", "ADLS storage account name")

storage_account = dbutils.widgets.get("storage_account")
silver_path = f"abfss://silver@{storage_account}.dfs.core.windows.net/transactions"
gold_txn_path = f"abfss://gold@{storage_account}.dfs.core.windows.net/transactions_features"
gold_account_path = f"abfss://gold@{storage_account}.dfs.core.windows.net/account_features"

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

silver = spark.read.format("delta").load(silver_path)

# COMMAND ----------

# MAGIC %md ### Transaction-level features

# COMMAND ----------

txn_features = (
    silver.withColumn("is_cross_currency", (F.col("payment_currency") != F.col("receiving_currency")).cast("int"))
    .withColumn("is_cross_bank", (F.col("from_bank") != F.col("to_bank")).cast("int"))
    .withColumn("amount_delta", F.abs(F.col("amount_paid") - F.col("amount_received")))
    .withColumn("hour_of_day", F.hour("txn_timestamp"))
)

# COMMAND ----------

# MAGIC %md ### Account-level rolling features (24h fan-in / fan-out / velocity)

# COMMAND ----------

outgoing = (
    txn_features.groupBy("from_account", "txn_date")
    .agg(
        F.count("*").alias("out_txn_count"),
        F.sum("amount_paid").alias("out_amount_sum"),
        F.countDistinct("to_account").alias("fan_out"),
    )
    .withColumnRenamed("from_account", "account")
)

incoming = (
    txn_features.groupBy("to_account", "txn_date")
    .agg(
        F.count("*").alias("in_txn_count"),
        F.sum("amount_received").alias("in_amount_sum"),
        F.countDistinct("from_account").alias("fan_in"),
    )
    .withColumnRenamed("to_account", "account")
)

account_features = outgoing.join(incoming, on=["account", "txn_date"], how="full_outer").na.fill(0)

# COMMAND ----------

(
    txn_features.write.format("delta")
    .mode("overwrite")
    .partitionBy("txn_date")
    .save(gold_txn_path)
)

(
    account_features.write.format("delta")
    .mode("overwrite")
    .partitionBy("txn_date")
    .save(gold_account_path)
)

spark.sql("CREATE SCHEMA IF NOT EXISTS aml_gold")
spark.sql(f"CREATE TABLE IF NOT EXISTS aml_gold.transactions_features USING DELTA LOCATION '{gold_txn_path}'")
spark.sql(f"CREATE TABLE IF NOT EXISTS aml_gold.account_features USING DELTA LOCATION '{gold_account_path}'")

print("Gold layer written:")
print(f"  {gold_txn_path}")
print(f"  {gold_account_path}")
