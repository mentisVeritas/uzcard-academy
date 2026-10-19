"""Shared DB helpers for customer churn project."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine


def load_dotenv() -> None:
    root = Path(__file__).resolve().parents[3]  # repo root
    for base in (root, Path(__file__).resolve().parents[1]):
        dotenv = base / ".env"
        if not dotenv.exists():
            continue
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        break


def get_dsn() -> str:
    load_dotenv()
    user = os.environ["DB_USER"]
    password = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ.get("DB_HOST", "thomas.proxy.rlwy.net")
    port = os.environ.get("DB_PORT", "51432")
    name = os.environ.get("DB_NAME", "academy_db")
    sslmode = os.environ.get("DB_SSLMODE", "require")
    return (
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        f"?sslmode={sslmode}"
    )


def get_engine():
    return create_engine(get_dsn())
