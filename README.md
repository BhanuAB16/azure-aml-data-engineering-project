# Azure Data Engineering — Anti-Money-Laundering (AML) Detection Pipeline

End-to-end data engineering project on Azure using the **IBM Transactions for
Anti-Money-Laundering (AML)** synthetic dataset
(Kaggle: `ealtman2019/ibm-transactions-for-anti-money-laundering-aml`).

The dataset contains synthetic bank-to-bank transactions labeled as
laundering / not-laundering, and comes in several sizes (`HI-Small`,
`HI-Medium`, `HI-Large`, `LI-Small`, `LI-Medium`, `LI-Large`). Start with
`HI-Small` for development.

## Architecture

Medallion (bronze / silver / gold) architecture on Azure:

```
Kaggle dataset
      │
      ▼
┌─────────────────┐   orchestrated by   ┌───────────────────┐
│  ADLS Gen2       │◀────────────────────│  Azure Data Factory │
│  (bronze/raw)    │                     └───────────────────┘
└─────────────────┘                                │
      │  PySpark (Databricks) — clean, dedupe,      │ triggers
      │  type-cast, standardize currencies           ▼
      ▼                                     ┌───────────────────┐
┌─────────────────┐                         │ Azure Databricks   │
│  ADLS Gen2       │◀────────────────────────│ notebooks (ETL +   │
│  (silver/clean)  │                         │ feature eng + ML)  │
└─────────────────┘                         └───────────────────┘
      │  aggregate, feature engineer
      │  (graph features: fan-in/out, velocity, etc.)
      ▼
┌─────────────────┐
│  ADLS Gen2       │
│  (gold/features) │
└─────────────────┘
      │
      ├──────────────► Azure Synapse SQL / Azure SQL DB (serving layer)
      │
      └──────────────► Power BI dashboard (AML monitoring)

Model artifacts (fraud/laundering classifier) tracked via MLflow on Databricks.
Secrets (Kaggle API key, storage keys) stored in Azure Key Vault.
```

## Repo layout

```
infra/          Bicep templates to provision all Azure resources
data/scripts/   Dataset download + upload-to-ADLS scripts
notebooks/      PySpark notebooks: bronze→silver→gold ETL + ML model
pipelines/      Azure Data Factory pipeline/dataset/linkedservice JSON
docs/           Additional design notes
```

## Setup

### 0. Prerequisites
- Azure subscription with Owner/Contributor access
- Azure CLI (`az`) logged in: `az login`
- Kaggle account + API token (`~/.kaggle/kaggle.json`) to pull the dataset
- Python 3.10+, `pip install -r data/scripts/requirements.txt`

### 1. Provision infrastructure
```bash
az group create -n rg-aml-dataeng -l eastus
az deployment group create \
  -g rg-aml-dataeng \
  -f infra/main.bicep \
  -p infra/main.parameters.json
```
This creates: ADLS Gen2 storage account (bronze/silver/gold containers),
Azure Data Factory, Azure Databricks workspace, Key Vault, and a Synapse
SQL / Azure SQL serving database.

> This step provisions **billed** Azure resources — review `infra/main.bicep`
> and the parameters file first, and confirm cost/region before running.

### 2. Download & land the raw dataset
```bash
python data/scripts/download_dataset.py --variant HI-Small
python data/scripts/upload_to_adls.py --account <storage_account_name> --variant HI-Small
```

### 3. Run the ETL
Import `notebooks/01_bronze_to_silver.py`, `notebooks/02_silver_to_gold.py`,
and `notebooks/03_train_aml_model.py` into the Databricks workspace (or run
via Databricks CLI / Jobs) — see `docs/notebooks.md`.

### 4. Orchestrate
Import the Data Factory pipeline in `pipelines/` (or `az datafactory
pipeline create`) to schedule the end-to-end run.

### 5. Serve & visualize
Point Power BI (or any BI tool) at the gold-layer table in the Synapse/SQL
serving database for AML monitoring dashboards.

## Status — deployed 2026-08-18

Live in resource group **rg-aml** (subscription "Projects", East US 2):

| Resource | Name |
|---|---|
| Storage account (ADLS Gen2) | `amldataengsthggybkyupgur` |
| Data Factory | `amldataeng-adf-hggybkyupgura` |
| Databricks workspace | `adb-7405606173363461.1.azuredatabricks.net` |
| Key Vault | `amldataeng-kv-hggybkyu` |

Raw dataset uploaded: `bronze/raw/HI-Small_Trans.csv` (476 MB).

**Azure SQL serving database was skipped** — `Microsoft.Sql` server
provisioning is restricted on this subscription in both East US 2 and East
US (`ProvisioningDisabled` — subscriptions typically need a support request
of type "Service and subscription limits" to lift this). The Bicep template
now takes it behind a `deploySqlDatabase` param (default `true`); redeploy
with `-p deploySqlDatabase=true` once quota is granted. In the meantime, the
gold Delta tables in ADLS can be queried directly via a Databricks SQL
warehouse or Azure Synapse serverless SQL — no dedicated SQL server needed.

A generated SQL admin password is already stored in Key Vault as secret
`sql-admin-password` (login: `amladmin`) for whenever the SQL database is
added.

### Next steps
1. Run `notebooks/01_bronze_to_silver.py` etc. in the Databricks workspace
   against storage account `amldataengsthggybkyupgur` (see `docs/notebooks.md`).
2. Optionally import the ADF pipeline in `pipelines/` to orchestrate it.
3. Optionally request a SQL quota increase and redeploy with
   `deploySqlDatabase=true` for a dedicated serving layer.
