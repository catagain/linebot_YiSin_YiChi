import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymysql

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

PROJECT_CONFIG = {
    "yiqi": {
        "base_dir": REPO_ROOT / "YiQi" / "linebot_for_JayWu-20251109jaywu_complete",
        "table_suffix": "yiqi",
    },
    "yisin": {
        "base_dir": REPO_ROOT / "YiSin" / "linebot_for_JayWu-20251109jaywu_complete",
        "table_suffix": "yisin",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate addresses.json and available_addresses.json into MySQL "
            "with project-specific tables."
        )
    )
    parser.add_argument("--project", choices=["yiqi", "yisin", "all"], default="all")
    parser.add_argument(
        "--dataset",
        choices=["case_names", "available_addresses", "all"],
        default="all",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional env file path. If omitted, script tries common .env locations.",
    )
    parser.add_argument("--host", help="MySQL host")
    parser.add_argument("--port", type=int, help="MySQL port")
    parser.add_argument("--user", help="MySQL user")
    parser.add_argument("--password", help="MySQL password")
    parser.add_argument("--db", help="MySQL database name")
    parser.add_argument("--charset", help="MySQL charset")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            "JSON file not found: %s (cwd=%s)" % (path, Path.cwd())
        )
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


def auto_load_env(selected_projects: List[str]) -> None:
    candidates = [Path.cwd() / ".env", REPO_ROOT / ".env"]
    for project in selected_projects:
        candidates.append(PROJECT_CONFIG[project]["base_dir"] / ".env")

    for candidate in candidates:
        if candidate.exists():
            load_env_file(candidate)
            return


def pick_setting(cli_value: Optional[str], env_names: List[str], default: Optional[str] = None) -> Optional[str]:
    if cli_value is not None and cli_value != "":
        return cli_value

    for env_name in env_names:
        env_value = os.getenv(env_name)
        if env_value is not None and env_value != "":
            return env_value

    return default


def get_mysql_connection(args: argparse.Namespace) -> pymysql.connections.Connection:
    host = pick_setting(args.host, ["DB_HOST"], "localhost")
    port_raw = pick_setting(str(args.port) if args.port else None, ["DB_PORT"], "3306")
    user = pick_setting(args.user, ["DB_USER", "DB_user"])
    password = pick_setting(args.password, ["DB_PASSWORD"])
    database = pick_setting(args.db, ["DB_NAME"])
    charset = pick_setting(args.charset, ["DB_CHARSET"], "utf8mb4")

    if not user or not database:
        raise ValueError(
            "Missing MySQL settings. Required: user and database.\n"
            "Provide one of: \n"
            "1) .env with DB_USER (or DB_user), DB_PASSWORD, DB_NAME, DB_HOST\n"
            "2) CLI args: --user --password --db --host"
        )

    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        db=database,
        port=int(port_raw),
        charset=charset,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def ensure_case_names_table(cursor: pymysql.cursors.Cursor, table_name: str) -> None:
    cursor.execute(
        f"""
CREATE TABLE IF NOT EXISTS `{table_name}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
"""
    )


def ensure_available_addresses_table(cursor: pymysql.cursors.Cursor, table_name: str) -> None:
    cursor.execute(
        f"""
CREATE TABLE IF NOT EXISTS `{table_name}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_address VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(50) NOT NULL,
    warranty_start_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
"""
    )


def normalize_date(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return date.fromisoformat(value).isoformat()
    raise ValueError("Unsupported warranty_start_date value: %s" % value)


def upsert_case_names(cursor: pymysql.cursors.Cursor, table_name: str, case_names: List[str]) -> int:
    count = 0
    sql = (
        f"INSERT INTO `{table_name}` (case_name) VALUES (%s) "
        "ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP"
    )

    for case_name in case_names:
        clean_case_name = str(case_name).strip()
        if not clean_case_name:
            continue
        cursor.execute(sql, (clean_case_name,))
        count += 1

    return count


def upsert_available_addresses(
    cursor: pymysql.cursors.Cursor,
    table_name: str,
    rows: List[Dict[str, Any]],
) -> int:
    count = 0
    sql = (
        f"INSERT INTO `{table_name}` (full_address, password, warranty_start_date) "
        "VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "password = VALUES(password), "
        "warranty_start_date = COALESCE(VALUES(warranty_start_date), warranty_start_date), "
        "updated_at = CURRENT_TIMESTAMP"
    )

    for row in rows:
        full_address = str(row.get("address", "")).strip()
        password = str(row.get("password", "")).strip()
        warranty_start_date = normalize_date(row.get("warranty_start_date"))

        if not full_address or not password:
            continue

        cursor.execute(sql, (full_address, password, warranty_start_date))
        count += 1

    return count


def migrate_project(conn: pymysql.connections.Connection, project_key: str, dataset: str) -> None:
    config = PROJECT_CONFIG[project_key]
    base_dir = config["base_dir"]
    suffix = config["table_suffix"]

    addresses_json = base_dir / "addresses.json"
    available_json = base_dir / "available_addresses.json"

    case_names_table = "case_names_%s" % suffix
    available_table = "available_addresses_%s" % suffix

    with conn.cursor() as cursor:
        if dataset in ("case_names", "all"):
            ensure_case_names_table(cursor, case_names_table)
            case_names = load_json(addresses_json)
            inserted = upsert_case_names(cursor, case_names_table, case_names)
            print("[%s] migrated case_names -> %s: %s rows" % (project_key, case_names_table, inserted))

        if dataset in ("available_addresses", "all"):
            ensure_available_addresses_table(cursor, available_table)
            available_rows = load_json(available_json)
            inserted = upsert_available_addresses(cursor, available_table, available_rows)
            print("[%s] migrated available_addresses -> %s: %s rows" % (project_key, available_table, inserted))

    conn.commit()


def main() -> None:
    args = parse_args()
    selected_projects = [args.project] if args.project != "all" else list(PROJECT_CONFIG.keys())

    if args.env_file:
        load_env_file(Path(args.env_file).expanduser().resolve())
    else:
        auto_load_env(selected_projects)

    conn = get_mysql_connection(args)
    try:
        for project_key in selected_projects:
            migrate_project(conn, project_key, args.dataset)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
