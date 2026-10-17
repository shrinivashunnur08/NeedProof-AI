"""Small SQLite store for the commerce loop demo (shops, requests, photo replies, demand).

All shops and listings are fictional demo data, labelled as such in the API.
"""
from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None
_CONN_PATH: str | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS shops (
  id TEXT PRIMARY KEY, city TEXT NOT NULL, name TEXT NOT NULL, area TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT NOT NULL, product TEXT NOT NULL,
  specs TEXT NOT NULL, price REAL NOT NULL, currency TEXT NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, city TEXT NOT NULL, product TEXT NOT NULL,
  specs TEXT NOT NULL, budget REAL, currency TEXT, language TEXT, raw_text TEXT,
  status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL, shop_id TEXT NOT NULL,
  price REAL, currency TEXT, stock INTEGER, claim TEXT NOT NULL, check_result TEXT NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS demand_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, city TEXT NOT NULL, product_key TEXT NOT NULL,
  product TEXT NOT NULL, budget REAL, currency TEXT, answered INTEGER NOT NULL,
  source TEXT NOT NULL, created_at TEXT NOT NULL);
"""

SHOPS = [
    ("sg-harbour", "singapore", "Harbour Tech (demo)", "Bugis"),
    ("sg-lioncity", "singapore", "Lion City Mobiles (demo)", "Orchard"),
    ("sg-marina", "singapore", "Marina Gadgets (demo)", "Jurong East"),
    ("sp-paulista", "sao-paulo", "Paulista Eletrônicos (demo)", "Bela Vista"),
    ("sp-centro", "sao-paulo", "Loja Centro Tech (demo)", "Centro"),
    ("sp-vila", "sao-paulo", "Vila Digital (demo)", "Vila Mariana"),
    ("mu-seaface", "mumbai", "Seaface Electronics (demo)", "Worli"),
    ("mu-gateway", "mumbai", "Gateway Mobiles (demo)", "Andheri"),
    ("mu-metro", "mumbai", "Metro Gadget Hub (demo)", "Dadar"),
]

CHARGER_65 = {"wattage_w": 65, "connector": "USB-C", "usb_pd": True}
CHARGER_45 = {"wattage_w": 45, "connector": "USB-C", "usb_pd": True}
CABLE = {"connector": "USB-C", "max_watts": 100}
LISTINGS = [
    ("sg-harbour", "65W USB-C PD laptop charger", CHARGER_65, 49, "SGD", 3),
    ("sg-lioncity", "65W USB-C PD GaN charger", CHARGER_65, 39, "SGD", 0),
    ("sg-marina", "45W USB-C PD charger", CHARGER_45, 29, "SGD", 5),
    ("sg-marina", "USB-C to USB-C cable 100W", CABLE, 15, "SGD", 9),
    ("sp-paulista", "Carregador USB-C PD 65W", CHARGER_65, 189, "BRL", 2),
    ("sp-centro", "Carregador GaN 65W USB-C PD", CHARGER_65, 149, "BRL", 0),
    ("sp-vila", "Carregador USB-C PD 45W", CHARGER_45, 99, "BRL", 4),
    ("mu-seaface", "65W USB-C PD laptop charger", CHARGER_65, 899, "INR", 3),
    ("mu-gateway", "65W GaN USB-C PD charger", CHARGER_65, 950, "INR", 2),
    ("mu-metro", "45W USB-C PD charger", CHARGER_45, 599, "INR", 6),
]

# Synthetic demand history so insights and forecasts have something to show.
_DEMAND_PRODUCTS = {
    "singapore": [("65w usb-c pd charger", "65W USB-C PD charger", 55, 0.35),
                  ("usb-c cable 100w", "USB-C cable 100W", 30, 0.8),
                  ("power bank 20000mah", "Power bank 20000mAh", 22, 0.5),
                  ("travel adapter uk", "Travel adapter (UK plug)", 14, 0.6)],
    "sao-paulo": [("65w usb-c pd charger", "Carregador 65W USB-C PD", 160, 0.3),
                  ("usb-c cable 100w", "Cabo USB-C 100W", 60, 0.7),
                  ("power bank 20000mah", "Power bank 20000mAh", 120, 0.45)],
    "mumbai": [("65w usb-c pd charger", "65W USB-C PD charger", 900, 0.4),
               ("usb-c cable 100w", "USB-C cable 100W", 300, 0.75),
               ("power bank 20000mah", "Power bank 20000mAh", 1500, 0.5)],
}
_CITY_CURRENCY = {"singapore": "SGD", "sao-paulo": "BRL", "mumbai": "INR"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path() -> str:
    default = Path(__file__).resolve().parents[2] / "commerce_loop.db"
    return os.environ.get("LOOP_DB_PATH", str(default))


def conn() -> sqlite3.Connection:
    global _CONN, _CONN_PATH
    with _LOCK:
        path = db_path()
        if _CONN is None or _CONN_PATH != path:
            _CONN = sqlite3.connect(path, check_same_thread=False)
            _CONN.row_factory = sqlite3.Row
            _CONN.executescript(SCHEMA)
            _CONN_PATH = path
            if _CONN.execute("SELECT COUNT(*) FROM shops").fetchone()[0] == 0:
                _seed(_CONN)
        return _CONN


def reset() -> None:
    with _LOCK:
        c = conn()
        for table in ("shops", "listings", "requests", "responses", "demand_events"):
            c.execute(f"DELETE FROM {table}")
        _seed(c)


def _seed(c: sqlite3.Connection) -> None:
    c.executemany("INSERT INTO shops VALUES (?,?,?,?)", SHOPS)
    c.executemany(
        "INSERT INTO listings (shop_id, product, specs, price, currency, stock) VALUES (?,?,?,?,?,?)",
        [(s, p, json.dumps(sp), pr, cur, st) for s, p, sp, pr, cur, st in LISTINGS],
    )
    rng = random.Random(42)
    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    rows = []
    for city, products in _DEMAND_PRODUCTS.items():
        for key, label, budget, answered_rate in products:
            for day in range(28, 0, -1):
                trend = 1.0 + (28 - day) / 28  # demand roughly doubles over four weeks
                weekend = 1.4 if (today - timedelta(days=day)).weekday() >= 5 else 1.0
                count = max(0, int(rng.gauss(1.6 * trend * weekend, 0.8)))
                for _ in range(count):
                    at = today - timedelta(days=day, minutes=rng.randint(0, 600))
                    rows.append((city, key, label, round(budget * rng.uniform(0.8, 1.2)), _CITY_CURRENCY[city],
                                 1 if rng.random() < answered_rate else 0, "synthetic_seed", at.isoformat(timespec="seconds")))
    c.executemany(
        "INSERT INTO demand_events (city, product_key, product, budget, currency, answered, source, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)", rows)
    c.commit()


def product_key(product: str, specs: dict | None = None) -> str:
    text = product.casefold()
    words = re.findall(r"[a-z0-9]+", text)
    watt = (specs or {}).get("wattage_w")
    if watt is None:
        m = re.search(r"(\d{2,3})\s*w\b", text)
        watt = int(m.group(1)) if m else None
    if any(w in words for w in ("charger", "carregador", "adapter", "चार्जर")) or "充电" in product or "चार्जर" in product:
        return f"{watt}w usb-c pd charger" if watt else "usb-c charger"
    if "cable" in words or "cabo" in words:
        return "usb-c cable 100w"
    if "power" in words and "bank" in words:
        return "power bank 20000mah"
    return " ".join(words[:5]) or "other"


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with _LOCK:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def execute(sql: str, params: tuple = ()) -> int:
    with _LOCK:
        c = conn()
        cur = c.execute(sql, params)
        c.commit()
        return int(cur.lastrowid or 0)


def shops_in_city(city: str) -> list[dict]:
    return rows("SELECT * FROM shops WHERE city=? ORDER BY name", (city,))


def shop(shop_id: str) -> dict | None:
    found = rows("SELECT * FROM shops WHERE id=?", (shop_id,))
    return found[0] if found else None


def listings_for(shop_id: str) -> list[dict]:
    out = rows("SELECT * FROM listings WHERE shop_id=?", (shop_id,))
    for item in out:
        item["specs"] = json.loads(item["specs"])
    return out


def create_request(city: str, product: str, specs: dict, budget: float | None, currency: str | None,
                   language: str, raw_text: str) -> int:
    rid = execute(
        "INSERT INTO requests (city, product, specs, budget, currency, language, raw_text, status, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (city, product, json.dumps(specs), budget, currency, language, raw_text[:500], "OPEN", now_iso()))
    record_demand(city, product, specs, budget, currency, answered=False)
    return rid


def record_demand(city: str, product: str, specs: dict | None, budget: float | None, currency: str | None,
                  answered: bool) -> None:
    execute(
        "INSERT INTO demand_events (city, product_key, product, budget, currency, answered, source, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (city, product_key(product, specs), product, budget, currency, 1 if answered else 0, "live_app", now_iso()))


def get_request(request_id: int) -> dict | None:
    found = rows("SELECT * FROM requests WHERE id=?", (request_id,))
    if not found:
        return None
    req = found[0]
    req["specs"] = json.loads(req["specs"])
    req["responses"] = responses_for(request_id)
    return req


def open_requests(city: str) -> list[dict]:
    out = rows("SELECT * FROM requests WHERE city=? ORDER BY id DESC LIMIT 30", (city,))
    for r in out:
        r["specs"] = json.loads(r["specs"])
        r["responses"] = responses_for(r["id"])
    return out


def responses_for(request_id: int) -> list[dict]:
    out = rows("SELECT r.*, s.name AS shop_name FROM responses r JOIN shops s ON s.id=r.shop_id"
               " WHERE request_id=? ORDER BY r.id", (request_id,))
    for r in out:
        r["claim"] = json.loads(r["claim"])
        r["check_result"] = json.loads(r["check_result"])
    return out


def add_response(request_id: int, shop_id: str, price: float | None, currency: str | None, stock: int | None,
                 claim: dict, check: dict, status: str) -> int:
    rid = execute(
        "INSERT INTO responses (request_id, shop_id, price, currency, stock, claim, check_result, status, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (request_id, shop_id, price, currency, stock, json.dumps(claim), json.dumps(check), status, now_iso()))
    if status == "PHOTO_MATCHES_REQUEST":
        execute("UPDATE requests SET status='ANSWERED' WHERE id=?", (request_id,))
        req = rows("SELECT * FROM requests WHERE id=?", (request_id,))[0]
        # Mark the demand as answered: the most recent unanswered live event for this need.
        execute("UPDATE demand_events SET answered=1 WHERE id=(SELECT id FROM demand_events WHERE city=? AND"
                " product=? AND answered=0 AND source='live_app' ORDER BY id DESC LIMIT 1)",
                (req["city"], req["product"]))
    return rid
