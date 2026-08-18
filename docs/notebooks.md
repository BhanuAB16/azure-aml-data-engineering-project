# Running the notebooks in Databricks

1. In the Databricks workspace, **Repos** > add this project's Git repo (or
   `Workspace > Import` each file individually with format "Source").
2. Attach each notebook to a cluster with Databricks Runtime ML (for
   `mlflow`/`pyspark.ml` support in `03_train_aml_model.py`).
3. Run in order, passing the `storage_account` widget value (the ADLS Gen2
   account name from the Bicep deployment output):
   - `01_bronze_to_silver.py`
   - `02_silver_to_gold.py`
   - `03_train_aml_model.py`
4. To automate, either use the ADF pipeline in `../pipelines/` (update the
   `notebookPath` values to match where you imported them) or create a
   Databricks Workflow/Job chaining the three notebooks directly.
