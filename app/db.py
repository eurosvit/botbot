import os, logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

_engine = None
_Session = None

def _coerce_psycopg3(url: str) -> str:
    # Force SQLAlchemy to use psycopg v3 driver
    parsed = urlparse(url)
    if parsed.scheme in ("postgres", "postgresql"):
        parsed = parsed._replace(scheme="postgresql+psycopg")
        return urlunparse(parsed)
    return url

def _ensure_ssl(url: str) -> str:
    # Append sslmode=require if missing
    parsed = urlparse(url)
    if parsed.scheme.startswith("postgresql+psycopg"):
        q = parse_qs(parsed.query)
        if "sslmode" not in q:
            q["sslmode"] = ["require"]
            new_query = urlencode(q, doseq=True)
            parsed = parsed._replace(query=new_query)
            return urlunparse(parsed)
    return url

def get_engine():
    global _engine, _Session
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        url = _coerce_psycopg3(url)
        url = _ensure_ssl(url)
        logging.info({"event":"db_create_engine_psycopg3", "url_scheme": url.split(':',1)[0]})
        _engine = create_engine(url, pool_pre_ping=True, future=True)
        _Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine

def get_session():
    if _Session is None:
        get_engine()
    return _Session()

def init_db():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS trade_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                direction TEXT,
                symbol TEXT,
                entry_price NUMERIC,
                exit_price NUMERIC,
                amount NUMERIC,
                profit NUMERIC,
                stop_loss NUMERIC,
                take_profit NUMERIC
            );
            CREATE TABLE IF NOT EXISTS salesdrive_events (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                payload JSONB NOT NULL
            );
            """
        ))
        logging.info({"event":"db_init_ok"})
