# Databricks notebook source
# MAGIC %md
# MAGIC # Train an AML (laundering) detection model
# MAGIC Trains a gradient-boosted tree classifier on the gold transaction
# MAGIC features, tracked with MLflow, to flag likely laundering transactions.

# COMMAND ----------

dbutils.widgets.text("storage_account", "", "ADLS storage account name")

storage_account = dbutils.widgets.get("storage_account")
gold_txn_path = f"abfss://gold@{storage_account}.dfs.core.windows.net/transactions_features"

# COMMAND ----------

import mlflow
from pyspark.ml import Pipeline
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import StringIndexer, VectorAssembler

df = spark.read.format("delta").load(gold_txn_path)

feature_cols = [
    "amount_paid",
    "amount_received",
    "amount_delta",
    "is_cross_currency",
    "is_cross_bank",
    "hour_of_day",
]
categorical_cols = ["payment_format"]

train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)

# COMMAND ----------

indexers = [
    StringIndexer(inputCol=c, outputCol=f"{c}_idx", handleInvalid="keep") for c in categorical_cols
]
assembler = VectorAssembler(
    inputCols=feature_cols + [f"{c}_idx" for c in categorical_cols],
    outputCol="features",
)
gbt = GBTClassifier(labelCol="is_laundering", featuresCol="features", maxIter=50, maxDepth=5, seed=42)

pipeline = Pipeline(stages=indexers + [assembler, gbt])

# COMMAND ----------

mlflow.pyspark.ml.autolog()

with mlflow.start_run(run_name="aml-gbt-classifier"):
    model = pipeline.fit(train_df)
    predictions = model.transform(test_df)

    evaluator = BinaryClassificationEvaluator(labelCol="is_laundering", metricName="areaUnderPR")
    auprc = evaluator.evaluate(predictions)
    auc_evaluator = BinaryClassificationEvaluator(labelCol="is_laundering", metricName="areaUnderROC")
    auroc = auc_evaluator.evaluate(predictions)

    mlflow.log_metric("test_auprc", auprc)
    mlflow.log_metric("test_auroc", auroc)
    print(f"Test AUPRC: {auprc:.4f}")
    print(f"Test AUROC: {auroc:.4f}")

    mlflow.spark.log_model(model, "model")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Notes
# MAGIC - The dataset is heavily imbalanced (laundering is rare) — AUPRC matters
# MAGIC   more than accuracy or AUROC alone. Consider class weighting or
# MAGIC   resampling for production use.
# MAGIC - Promote the best run to the MLflow Model Registry and serve via a
# MAGIC   Databricks model-serving endpoint or batch-score into the gold layer.
