import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

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
    parser.add_argument(
        "--env-file",
        default=".env.sqlserver",
        help="Optional env file path. Default: .env.sqlserver",
    )
    parser.add_argument("--host", help="SQL Server host.")
    parser.add_argument("--instance", help="SQL Server instance name, e.g. SQLEXPRESS.")
    parser.add_argument("--port", help="SQL Server port. Default: 1433")
    parser.add_argument("--db", help="SQL Server database name.")
    parser.add_argument("--user", help="SQL Server username.")
    parser.add_argument("--password", help="SQL Server password.")
    parser.add_argument("--driver", help="ODBC driver name.")
    parser.add_argument("--encrypt", choices=["yes", "no"], help="Encrypt connection.")
    parser.add_argument(
        "--trust-cert",
        choices=["yes", "no"],
        help="Trust SQL Server certificate.",
    )
    parser.add_argument(
        "--list-drivers",
        action="store_true",
        help="Print installed ODBC drivers and exit.",
    )
    return parser.parse_args()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def pick_setting(cli_value: Optional[str], env_name: str, default: Optional[str] = None) -> Optional[str]:
    if cli_value is not None and cli_value != "":
        return cli_value
    env_value = os.getenv(env_name)
    if env_value is not None and env_value != "":
        return env_value
    return default


def resolve_sqlserver_driver(preferred_driver: Optional[str]) -> str:
    installed = [d.strip() for d in pyodbc.drivers() if d and d.strip()]
    installed_set = set(installed)

    if preferred_driver and preferred_driver in installed_set:
        return preferred_driver

    candidates = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server",
    ]

    for candidate in candidates:
        if candidate in installed_set:
            return candidate

    if installed:
        raise ValueError(
            "No SQL Server ODBC driver found. Installed drivers are: "
            + ", ".join(installed)
        )

    raise ValueError(
        "No ODBC drivers detected by pyodbc. Please install Microsoft ODBC Driver 18 for SQL Server."
    )


def get_sqlserver_connection(args: argparse.Namespace) -> pyodbc.Connection:
    requested_driver = pick_setting(args.driver, "SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    server = pick_setting(args.host, "SQLSERVER_HOST")
    instance = pick_setting(args.instance, "SQLSERVER_INSTANCE")
    port = pick_setting(args.port, "SQLSERVER_PORT", "1433")
    database = pick_setting(args.db, "SQLSERVER_DB")
    user = pick_setting(args.user, "SQLSERVER_USER")
    password = pick_setting(args.password, "SQLSERVER_PASSWORD")
    encrypt = pick_setting(args.encrypt, "SQLSERVER_ENCRYPT", "yes")
    trust_cert = pick_setting(args.trust_cert, "SQLSERVER_TRUST_CERT", "yes")
    driver = resolve_sqlserver_driver(requested_driver)

    if not server or not database:
        raise ValueError(
            "Missing SQL Server settings. Please provide host/database by one of the following ways:\n"
            "1) Env vars: SQLSERVER_HOST and SQLSERVER_DB\n"
            "2) CLI args: --host <host> --db <database>\n"
            "3) Env file: set values in --env-file (default .env.sqlserver)"
        )

    if instance:
        server_target = f"{server}\\{instance}"
    else:
        server_target = f"{server},{port}"

    # The legacy "SQL Server" ODBC driver does not support Encrypt/TrustServerCertificate keywords.
    is_legacy_sql_driver = driver.strip().lower() == "sql server"
    extra_security = ""
    if not is_legacy_sql_driver:
        extra_security = f"Encrypt={encrypt};TrustServerCertificate={trust_cert};"

    if user and password:
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server_target};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            f"{extra_security}"
        )
    else:
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server_target};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            f"{extra_security}"
        )

    try:
        return pyodbc.connect(conn_str)
    except pyodbc.InterfaceError as e:
        installed = [d.strip() for d in pyodbc.drivers() if d and d.strip()]
        raise ValueError(
            "ODBC connection failed (IM002). Most likely SQL Server ODBC driver is missing or mismatch. "
            f"Requested driver: {driver}. Installed drivers: {installed}"
        ) from e


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

    if args.list_drivers:
        drivers = [d.strip() for d in pyodbc.drivers() if d and d.strip()]
        if drivers:
            print("Installed ODBC drivers:")
            for d in drivers:
                print(f"- {d}")
        else:
            print("No ODBC drivers detected.")
        return

    if args.env_file:
        load_env_file(Path(args.env_file))

    selected_projects = [args.project] if args.project != "all" else list(PROJECT_CONFIG.keys())

    conn = get_sqlserver_connection(args)
    try:
        for project_key in selected_projects:
            migrate_project(conn, project_key, args.dataset)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
