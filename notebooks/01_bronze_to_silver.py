# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze -> Silver: clean & standardize IBM AML transactions
# MAGIC Reads raw CSV landed in the `bronze` ADLS container, cleans/types/dedupes it,
# MAGIC and writes a Delta table to the `silver` container.

# COMMAND ----------

dbutils.widgets.text("storage_account", "", "ADLS storage account name")
dbutils.widgets.text("variant", "HI-Small", "Dataset variant")

storage_account = dbutils.widgets.get("storage_account")
variant = dbutils.widgets.get("variant")

bronze_path = f"abfss://bronze@{storage_account}.dfs.core.windows.net/raw"
silver_path = f"abfss://silver@{storage_account}.dfs.core.windows.net/transactions"

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, TimestampType

raw = (
    spark.read.option("header", True)
    .option("inferSchema", True)
    .csv(f"{bronze_path}/*{variant}*Trans*.csv")
)

# Source columns (IBM AML dataset, in order): Timestamp, From Bank, Account,
# To Bank, Account, Amount Received, Receiving Currency, Amount Paid,
# Payment Currency, Payment Format, Is Laundering
# NOTE: the raw CSV header has "Account" twice (from- and to-account), which
# Spark cannot disambiguate by name — rename positionally via toDF instead.
COLUMN_ORDER = [
    "txn_timestamp",
    "from_bank",
    "from_account",
    "to_bank",
    "to_account",
    "amount_received",
    "receiving_currency",
    "amount_paid",
    "payment_currency",
    "payment_format",
    "is_laundering",
]
renamed = raw.toDF(*COLUMN_ORDER)

# COMMAND ----------

cleaned = (
    renamed.withColumn("txn_timestamp", F.to_timestamp("txn_timestamp", "yyyy/MM/dd HH:mm"))
    .withColumn("amount_paid", F.col("amount_paid").cast(DoubleType()))
    .withColumn("amount_received", F.col("amount_received").cast(DoubleType()))
    .withColumn("is_laundering", F.col("is_laundering").cast("int"))
    .dropna(subset=["txn_timestamp", "from_account", "to_account", "amount_paid"])
    .dropDuplicates(["txn_timestamp", "from_account", "to_account", "amount_paid", "payment_format"])
    .withColumn("txn_date", F.to_date("txn_timestamp"))
)

print(f"Bronze rows: {raw.count():,}  ->  Silver rows: {cleaned.count():,}")

# COMMAND ----------

(
    cleaned.write.format("delta")
    .mode("overwrite")
    .partitionBy("txn_date")
    .save(silver_path)
)

spark.sql("CREATE SCHEMA IF NOT EXISTS aml_silver")
spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS aml_silver.transactions
    USING DELTA
    LOCATION '{silver_path}'
    """
)

print(f"Wrote silver Delta table to {silver_path}")
