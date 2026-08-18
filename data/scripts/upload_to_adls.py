"""Upload locally-downloaded AML dataset files into the ADLS Gen2 'bronze' container.

Authenticates with Azure via DefaultAzureCredential (uses `az login` session,
managed identity, or environment credentials — whichever is available).

Usage:
    python upload_to_adls.py --account <storage_account_name> --variant HI-Small
"""
import argparse
import pathlib

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True, help="ADLS Gen2 storage account name")
    parser.add_argument("--container", default="bronze", help="Target container (default: bronze)")
    parser.add_argument(
        "--source",
        default=str(pathlib.Path(__file__).resolve().parents[1] / "raw"),
        help="Local directory containing the downloaded dataset files",
    )
    parser.add_argument("--variant", default="HI-Small", help="Only upload files matching this variant name")
    args = parser.parse_args()

    source_dir = pathlib.Path(args.source)
    files = sorted(source_dir.glob(f"*{args.variant}*"))
    if not files:
        raise SystemExit(f"No files matching '*{args.variant}*' found in {source_dir}. Run download_dataset.py first.")

    account_url = f"https://{args.account}.dfs.core.windows.net"
    credential = DefaultAzureCredential()
    service_client = DataLakeServiceClient(account_url=account_url, credential=credential)
    fs_client = service_client.get_file_system_client(args.container)

    for f in files:
        remote_path = f"raw/{f.name}"
        print(f"Uploading {f} -> {args.container}/{remote_path} ...")
        file_client = fs_client.get_file_client(remote_path)
        with open(f, "rb") as fh:
            data = fh.read()
        file_client.upload_data(data, overwrite=True)

    print(f"Uploaded {len(files)} file(s) to {args.container}/raw/ in account {args.account}.")


if __name__ == "__main__":
    main()
