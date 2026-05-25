import argparse
import json
import os
from datetime import date
from pathlib import Path

import pyodbc

PROJECT_CONFIG = {
    "yiqi": {
        "base_dir": Path("YiQi/linebot_for_JayWu-20251109jaywu_complete"),
        "table_suffix": "yiqi",
    },
    "yisin": {
        "base_dir": Path("YiSin/linebot_for_JayWu-20251109jaywu_complete"),
        "table_suffix": "yisin",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate addresses.json and available_addresses.json into SQL Server "
            "with project-specific tables."
        )
    )
    parser.add_argument(
        "--project",
        choices=["yiqi", "yisin", "all"],
        default="all",
        help="Select which project data to migrate.",
    )
    parser.add_argument(
        "--dataset",
        choices=["case_names", "available_addresses", "all"],
        default="all",
        help="Select which JSON dataset to migrate.",
    )
    return parser.parse_args()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_sqlserver_connection() -> pyodbc.Connection:
    driver = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("SQLSERVER_HOST")
    port = os.getenv("SQLSERVER_PORT", "1433")
    database = os.getenv("SQLSERVER_DB")
    user = os.getenv("SQLSERVER_USER")
    password = os.getenv("SQLSERVER_PASSWORD")
    encrypt = os.getenv("SQLSERVER_ENCRYPT", "yes")
    trust_cert = os.getenv("SQLSERVER_TRUST_CERT", "yes")

    if not server or not database:
        raise ValueError("SQLSERVER_HOST and SQLSERVER_DB are required in environment variables.")

    if user and password:
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust_cert};"
        )
    else:
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust_cert};"
        )

    return pyodbc.connect(conn_str)


def ensure_case_names_table(cursor: pyodbc.Cursor, table_name: str) -> None:
    cursor.execute(
        f"""
IF OBJECT_ID(N'dbo.{table_name}', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.{table_name} (
        id INT IDENTITY(1,1) PRIMARY KEY,
        case_name NVARCHAR(255) NOT NULL UNIQUE,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
"""
    )


def ensure_available_addresses_table(cursor: pyodbc.Cursor, table_name: str) -> None:
    cursor.execute(
        f"""
IF OBJECT_ID(N'dbo.{table_name}', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.{table_name} (
        id INT IDENTITY(1,1) PRIMARY KEY,
        full_address NVARCHAR(255) NOT NULL UNIQUE,
        password NVARCHAR(50) NOT NULL,
        warranty_start_date DATE NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
"""
    )


def normalize_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported warranty_start_date value: {value}")


def upsert_case_names(cursor: pyodbc.Cursor, table_name: str, case_names: list[str]) -> int:
    count = 0
    for case_name in case_names:
        clean_case_name = str(case_name).strip()
        if not clean_case_name:
            continue

        cursor.execute(
            f"""
MERGE dbo.{table_name} AS target
USING (SELECT ? AS case_name) AS source
ON target.case_name = source.case_name
WHEN MATCHED THEN
    UPDATE SET updated_at = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (case_name) VALUES (source.case_name);
""",
            clean_case_name,
        )
        count += 1
    return count


def upsert_available_addresses(cursor: pyodbc.Cursor, table_name: str, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        full_address = str(row.get("address", "")).strip()
        password = str(row.get("password", "")).strip()
        warranty_start_date = normalize_date(row.get("warranty_start_date"))

        if not full_address or not password:
            continue

        cursor.execute(
            f"""
MERGE dbo.{table_name} AS target
USING (SELECT ? AS full_address, ? AS password, ? AS warranty_start_date) AS source
ON target.full_address = source.full_address
WHEN MATCHED THEN
    UPDATE SET
        password = source.password,
        warranty_start_date = COALESCE(source.warranty_start_date, target.warranty_start_date),
        updated_at = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (full_address, password, warranty_start_date)
    VALUES (source.full_address, source.password, source.warranty_start_date);
""",
            full_address,
            password,
            warranty_start_date,
        )
        count += 1
    return count


def migrate_project(conn: pyodbc.Connection, project_key: str, dataset: str) -> None:
    config = PROJECT_CONFIG[project_key]
    base_dir = config["base_dir"]
    suffix = config["table_suffix"]

    addresses_json = base_dir / "addresses.json"
    available_json = base_dir / "available_addresses.json"

    case_names_table = f"case_names_{suffix}"
    available_table = f"available_addresses_{suffix}"

    with conn.cursor() as cursor:
        if dataset in ("case_names", "all"):
            ensure_case_names_table(cursor, case_names_table)
            case_names = load_json(addresses_json)
            inserted = upsert_case_names(cursor, case_names_table, case_names)
            print(f"[{project_key}] migrated case_names -> {case_names_table}: {inserted} rows")

        if dataset in ("available_addresses", "all"):
            ensure_available_addresses_table(cursor, available_table)
            available_rows = load_json(available_json)
            inserted = upsert_available_addresses(cursor, available_table, available_rows)
            print(f"[{project_key}] migrated available_addresses -> {available_table}: {inserted} rows")

    conn.commit()


def main() -> None:
    args = parse_args()
    selected_projects = [args.project] if args.project != "all" else list(PROJECT_CONFIG.keys())

    conn = get_sqlserver_connection()
    try:
        for project_key in selected_projects:
            migrate_project(conn, project_key, args.dataset)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
