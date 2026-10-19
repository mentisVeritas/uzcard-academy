"""Shared DB helpers for customer segments project."""

from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


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
        return


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
    return create_engine(
        get_dsn(),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "connect_timeout": 20,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )


def read_sql(sql, retries: int = 5, pause: float = 8.0):
    """pd.read_sql with retries — Railway proxy drops idle/new connections."""
    import pandas as pd
    from sqlalchemy import text

    last = None
    for attempt in range(1, retries + 1):
        engine = get_engine()
        try:
            return pd.read_sql(text(sql) if isinstance(sql, str) else sql, engine)
        except OperationalError as exc:
            last = exc
            print(f"DB connect failed ({attempt}/{retries}), retry in {pause:.0f}s")
            time.sleep(pause)
            pause *= 1.4
        finally:
            engine.dispose()
    raise last

