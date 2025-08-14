import os, logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

_engine=None; _Session=None

def _coerce(url):
    p=urlparse(url)
    return urlunparse(p._replace(scheme="postgresql+psycopg")) if p.scheme in ("postgres","postgresql") else url

def _ensure_ssl(url):
    p=urlparse(url)
    if p.scheme.startswith("postgresql+psycopg"):
        q=parse_qs(p.query); 
        if "sslmode" not in q: q["sslmode"]=["require"]
        p=p._replace(query=urlencode(q,doseq=True))
    return urlunparse(p)

def get_engine():
    global _engine,_Session
    if _engine is None:
        url=os.getenv("DATABASE_URL"); 
        if not url: raise RuntimeError("DATABASE_URL is not set")
        url=_ensure_ssl(_coerce(url)); logging.info("{'event': 'db_engine'}")
        _engine=create_engine(url, pool_pre_ping=True, future=True)
        _Session=sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine

def get_session():
    if _Session is None: get_engine()
    return _Session()

def migrate():
    eng=get_engine()
    with eng.begin() as c:
        c.execute(text("""CREATE TABLE IF NOT EXISTS salesdrive_events(
            id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), payload JSONB NOT NULL);"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS orders(
            id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());"""))
        for sql in (
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_id TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS amount_uah NUMERIC",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS brand TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS utm_campaign TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS status TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipped_at TIMESTAMPTZ"
        ): c.execute(text(sql))
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_shipped ON orders(shipped_at)"))
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)"))
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_campaign ON orders(utm_campaign)"))
        c.execute(text("""CREATE TABLE IF NOT EXISTS ad_stats(
            id SERIAL PRIMARY KEY, stat_date DATE NOT NULL, campaign TEXT NOT NULL, cost NUMERIC NOT NULL,
            currency TEXT NOT NULL DEFAULT 'UAH', clicks INTEGER NOT NULL DEFAULT 0, impressions INTEGER NOT NULL DEFAULT 0,
            UNIQUE(stat_date,campaign));"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS daily_reports(
            day DATE PRIMARY KEY,
            orders_count INTEGER, orders_ads_count INTEGER, sales_total NUMERIC, avg_check NUMERIC,
            ad_cost NUMERIC, manager_cost NUMERIC, avg_margin NUMERIC, gross_profit NUMERIC, net_profit NUMERIC,
            processing_orders_count INTEGER, processing_amount NUMERIC,
            real_sales_count INTEGER, real_sales_amount NUMERIC, real_avg_check NUMERIC, real_gross_profit NUMERIC,
            clarity_json JSONB);"""))
