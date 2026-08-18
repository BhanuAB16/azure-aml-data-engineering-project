"""Download the IBM Transactions for AML (Anti-Money-Laundering) dataset from Kaggle.

Requires a Kaggle API token at ~/.kaggle/kaggle.json (https://www.kaggle.com/settings -> API -> Create New Token).

Usage:
    python download_dataset.py --variant HI-Small --dest ../raw
"""
import argparse
import pathlib
import zipfile

KAGGLE_DATASET = "ealtman2019/ibm-transactions-for-anti-money-laundering-aml"

VARIANTS = ["HI-Small", "HI-Medium", "HI-Large", "LI-Small", "LI-Medium", "LI-Large"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=VARIANTS,
        default="HI-Small",
        help="Dataset size/variant to keep after download (default: HI-Small, smallest).",
    )
    parser.add_argument(
        "--dest",
        default=str(pathlib.Path(__file__).resolve().parents[1] / "raw"),
        help="Directory to extract the dataset into.",
    )
    args = parser.parse_args()

    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    from kaggle.api.kaggle_api_extended import KaggleApi  # imported here so --help works without credentials

    api = KaggleApi()
    api.authenticate()

    print(f"Downloading {KAGGLE_DATASET} to {dest} ...")
    api.dataset_download_files(KAGGLE_DATASET, path=str(dest), unzip=False)

    zip_path = dest / f"{KAGGLE_DATASET.split('/')[-1]}.zip"
    if zip_path.exists():
        print(f"Extracting {zip_path.name} ...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
        zip_path.unlink()

    matches = sorted(dest.glob(f"*{args.variant}*"))
    print(f"Done. Files matching variant '{args.variant}':")
    for m in matches:
        print(f"  {m}")
    if not matches:
        print(f"  (none found — inspect {dest} for the actual filenames the dataset ships with)")


if __name__ == "__main__":
    main()
