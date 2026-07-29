"""Load the Instacart raw CSVs into BigQuery.

This is the BigQuery counterpart to src/database_loader.py, which loads the same
files into local PostgreSQL. Both loaders produce the same five raw tables with the
same column names, so the dbt project runs unchanged against either target.

The script shells out to the `bq` and `gcloud storage` CLIs rather than using the
Python client so that the exact commands are inspectable and reproducible. Run with
--dry-run to print every command without executing anything; that mode needs no
credentials and is what CI and code review use to check this file.

Usage
-----
    python ingestion/load_bigquery.py --dry-run
    python ingestion/load_bigquery.py --project my-gcp-project --dataset instacart_raw
    python ingestion/load_bigquery.py --project my-gcp-project --dataset instacart_raw \
        --gcs-bucket my-staging-bucket

Files larger than a few hundred MB should go through --gcs-bucket: direct local
uploads to `bq load` are slower and less resilient than staging in Cloud Storage
first, and order_products.csv is ~574 MB.
"""

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"

# Explicit schemas. BigQuery autodetect is deliberately not used: it samples rows and
# can infer INT64 for a column that is empty early on and float later
# (days_since_prior_order is blank for every customer's first order).
TABLE_SPECS = [
    {
        "table": "departments",
        "csv": DATA_RAW / "departments.csv",
        "schema": "department_id:INT64,department:STRING",
    },
    {
        "table": "aisles",
        "csv": DATA_RAW / "aisles.csv",
        "schema": "aisle_id:INT64,aisle:STRING",
    },
    {
        "table": "products",
        "csv": DATA_RAW / "products.csv",
        "schema": "product_id:INT64,product_name:STRING,aisle_id:INT64,department_id:INT64",
    },
    {
        "table": "orders",
        "csv": DATA_RAW / "orders.csv",
        "schema": (
            "order_id:INT64,user_id:INT64,eval_set:STRING,order_number:INT64,"
            "order_dow:INT64,order_hour_of_day:INT64,days_since_prior_order:FLOAT64"
        ),
    },
    {
        "table": "order_products",
        "csv": DATA_RAW / "order_products.csv",
        "schema": (
            "order_id:INT64,product_id:INT64,add_to_cart_order:INT64,reordered:INT64"
        ),
    },
]


def csv_row_count(csv_path):
    """Count data rows in a CSV, excluding the header."""
    with csv_path.open("r", newline="") as file:
        return max(sum(1 for _ in file) - 1, 0)


def ensure_combined_order_products(rebuild=False):
    """Union order_products__prior.csv and order_products__train.csv.

    Mirrors src/database_loader.py so both warehouses receive an identical fact source.
    The Kaggle `test` split has no product labels and is intentionally excluded.
    """
    prior_path = DATA_RAW / "order_products__prior.csv"
    train_path = DATA_RAW / "order_products__train.csv"
    combined_path = DATA_RAW / "order_products.csv"

    if combined_path.exists() and not rebuild:
        print(f"Using existing {combined_path.relative_to(ROOT)}")
        return combined_path

    print(f"Building {combined_path.relative_to(ROOT)} from prior/train files")
    with combined_path.open("w", newline="") as output_file:
        writer = None
        for source_path in (prior_path, train_path):
            with source_path.open("r", newline="") as input_file:
                reader = csv.reader(input_file)
                header = next(reader)
                if writer is None:
                    writer = csv.writer(output_file)
                    writer.writerow(header)
                for row in reader:
                    writer.writerow(row)

    return combined_path


def run(command, dry_run):
    """Print a command, and execute it unless this is a dry run."""
    printable = " ".join(command)
    print(f"  $ {printable}")
    if dry_run:
        return None
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {printable}\n{result.stderr.strip()}")
    return result.stdout.strip()


def create_dataset(project, dataset, location, dry_run):
    print(f"\nEnsuring dataset {project}:{dataset} exists in {location}")
    # `bq mk` exits non-zero when the dataset already exists, so this is the one call
    # allowed to fail; --force makes it a no-op on an existing dataset.
    run(
        [
            "bq",
            "--project_id",
            project,
            "mk",
            "--force",
            "--location",
            location,
            "--dataset",
            f"{project}:{dataset}",
        ],
        dry_run,
    )


def stage_to_gcs(spec, bucket, dry_run):
    """Copy a CSV into Cloud Storage and return its gs:// URI."""
    uri = f"gs://{bucket}/instacart/raw/{spec['csv'].name}"
    run(["gcloud", "storage", "cp", str(spec["csv"]), uri], dry_run)
    return uri


def load_table(spec, project, dataset, source, dry_run):
    """Load one CSV into one BigQuery table, replacing whatever was there.

    --replace keeps the load idempotent: rerunning never appends duplicate rows.
    """
    print(f"\nLoading {spec['table']}")
    run(
        [
            "bq",
            "--project_id",
            project,
            "load",
            "--source_format=CSV",
            "--skip_leading_rows=1",
            "--replace",
            f"{dataset}.{spec['table']}",
            source,
            spec["schema"],
        ],
        dry_run,
    )


def validate_row_counts(project, dataset, dry_run):
    """Compare BigQuery row counts against the source CSVs."""
    print("\nRow-count validation")
    failures = []
    for spec in TABLE_SPECS:
        expected = csv_row_count(spec["csv"]) if spec["csv"].exists() else None
        query = f"SELECT COUNT(*) AS row_count FROM `{project}.{dataset}.{spec['table']}`"
        output = run(
            [
                "bq",
                "--project_id",
                project,
                "query",
                "--use_legacy_sql=false",
                "--format=csv",
                query,
            ],
            dry_run,
        )

        if dry_run:
            continue

        actual = int(output.splitlines()[-1])
        status = "PASS" if expected == actual else "FAIL"
        print(f"{status}: {spec['table']} expected={expected:,} actual={actual:,}")
        if status == "FAIL":
            failures.append(spec["table"])

    if failures:
        raise RuntimeError(f"Row-count validation failed for: {', '.join(failures)}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load Instacart CSVs into a BigQuery raw dataset."
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GCP_PROJECT"),
        help="GCP project id. Defaults to the GCP_PROJECT environment variable.",
    )
    parser.add_argument(
        "--dataset",
        default=os.getenv("BQ_RAW_DATASET", "instacart_raw"),
        help="BigQuery dataset for the raw tables. Defaults to BQ_RAW_DATASET or instacart_raw.",
    )
    parser.add_argument(
        "--location",
        default=os.getenv("BQ_LOCATION", "US"),
        help="BigQuery dataset location. Defaults to BQ_LOCATION or US.",
    )
    parser.add_argument(
        "--gcs-bucket",
        default=os.getenv("GCS_STAGING_BUCKET"),
        help="Stage CSVs in this Cloud Storage bucket before loading. Recommended for the ~574 MB order_products.csv.",
    )
    parser.add_argument(
        "--rebuild-order-products",
        action="store_true",
        help="Rebuild data/raw/order_products.csv from the prior/train source files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print every command without executing it. Requires no credentials.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.project and not args.dry_run:
        sys.exit("A --project is required (or set GCP_PROJECT). Use --dry-run to preview.")

    project = args.project or "YOUR_GCP_PROJECT"

    if args.dry_run:
        print("DRY RUN - printing commands only, nothing will be executed.\n")
    else:
        ensure_combined_order_products(rebuild=args.rebuild_order_products)

    missing = [
        spec["csv"].name for spec in TABLE_SPECS if not spec["csv"].exists()
    ]
    if missing and not args.dry_run:
        raise FileNotFoundError(f"Missing required CSVs: {', '.join(missing)}")
    if missing:
        print(f"Note: not present locally, commands shown anyway: {', '.join(missing)}\n")

    create_dataset(project, args.dataset, args.location, args.dry_run)

    for spec in TABLE_SPECS:
        if args.gcs_bucket:
            source = stage_to_gcs(spec, args.gcs_bucket, args.dry_run)
        else:
            source = str(spec["csv"])
        load_table(spec, project, args.dataset, source, args.dry_run)

    validate_row_counts(project, args.dataset, args.dry_run)

    if args.dry_run:
        print("\nDry run complete. Rerun without --dry-run to execute.")
    else:
        print("\nBigQuery raw warehouse load complete")


if __name__ == "__main__":
    main()
