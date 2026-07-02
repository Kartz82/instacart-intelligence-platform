import argparse
import csv
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"
load_dotenv(ROOT / ".env")

TABLE_LOAD_ORDER = [
    ("raw.departments", DATA_RAW / "departments.csv"),
    ("raw.aisles", DATA_RAW / "aisles.csv"),
    ("raw.products", DATA_RAW / "products.csv"),
    ("raw.orders", DATA_RAW / "orders.csv"),
    ("raw.order_products", DATA_RAW / "order_products.csv"),
]

TRUNCATE_ORDER = [
    "raw.order_products",
    "raw.orders",
    "raw.products",
    "raw.aisles",
    "raw.departments",
]


def env(name, default):
    return os.getenv(name, default)


def get_connection():
    return psycopg2.connect(
        dbname=env("POSTGRES_DB", "instacart_db"),
        user=env("POSTGRES_USER", "postgres"),
        password=env("POSTGRES_PASSWORD", "postgres"),
        host=env("POSTGRES_HOST", "localhost"),
        port=env("POSTGRES_PORT", "5434"),
    )


def run_schema(conn):
    with conn.cursor() as cursor:
        cursor.execute(SCHEMA_SQL.read_text())
    conn.commit()
    print(f"Applied schema from {SCHEMA_SQL.relative_to(ROOT)}")


def truncate_raw_tables(conn):
    tables = ", ".join(TRUNCATE_ORDER)
    with conn.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE;")
    conn.commit()
    print("Truncated raw tables for a clean reload")


def csv_row_count(csv_path):
    with csv_path.open("r", newline="") as file:
        return max(sum(1 for _ in file) - 1, 0)


def ensure_combined_order_products(rebuild=False):
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


def copy_csv(conn, table_name, csv_path):
    row_count = csv_row_count(csv_path)
    sql = f"COPY {table_name} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    with conn.cursor() as cursor:
        with csv_path.open("r", newline="") as file:
            cursor.copy_expert(sql, file)
    conn.commit()
    print(f"Loaded {row_count:,} rows into {table_name}")


def load_raw_tables(conn):
    for table_name, csv_path in TABLE_LOAD_ORDER:
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing required CSV: {csv_path}")
        copy_csv(conn, table_name, csv_path)


def database_row_count(conn, table_name):
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        return cursor.fetchone()[0]


def validate_row_counts(conn):
    results = []
    for table_name, csv_path in TABLE_LOAD_ORDER:
        expected = csv_row_count(csv_path)
        actual = database_row_count(conn, table_name)
        status = "PASS" if expected == actual else "FAIL"
        results.append((status, table_name, expected, actual))

    print("\nRow-count validation")
    for status, table_name, expected, actual in results:
        print(
            f"{status}: {table_name} expected={expected:,} actual={actual:,}"
        )

    failures = [result for result in results if result[0] != "PASS"]
    if failures:
        raise RuntimeError("Row-count validation failed")


def validate_basic_integrity(conn):
    checks = {
        "orders primary key uniqueness": """
            SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM raw.orders;
        """,
        "products primary key uniqueness": """
            SELECT COUNT(*) - COUNT(DISTINCT product_id) FROM raw.products;
        """,
        "order_products primary key uniqueness": """
            SELECT COUNT(*) - COUNT(DISTINCT (order_id, product_id))
            FROM raw.order_products;
        """,
        "invalid reordered values": """
            SELECT COUNT(*) FROM raw.order_products
            WHERE reordered NOT IN (0, 1);
        """,
    }

    print("\nBasic integrity validation")
    with conn.cursor() as cursor:
        for check_name, sql in checks.items():
            cursor.execute(sql)
            invalid_count = cursor.fetchone()[0]
            status = "PASS" if invalid_count == 0 else "FAIL"
            print(f"{status}: {check_name} invalid_count={invalid_count:,}")
            if invalid_count != 0:
                raise RuntimeError(f"Integrity validation failed: {check_name}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load Instacart CSVs into the local PostgreSQL raw schema."
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Apply sql/schema.sql without truncating or loading data.",
    )
    parser.add_argument(
        "--rebuild-order-products",
        action="store_true",
        help="Rebuild data/raw/order_products.csv from prior/train source files.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    conn = get_connection()
    try:
        run_schema(conn)

        if args.schema_only:
            print("Schema-only mode complete")
            return

        ensure_combined_order_products(rebuild=args.rebuild_order_products)
        truncate_raw_tables(conn)
        load_raw_tables(conn)
        validate_row_counts(conn)
        validate_basic_integrity(conn)
    finally:
        conn.close()

    print("\nPostgreSQL raw warehouse load complete")


if __name__ == "__main__":
    main()
