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
  id TEXT PRIMARY KEY, city TEXT NOT NULL, name TEXT NOT NULL, area TEXT NOT NULL,
  lat REAL, lng REAL, source TEXT NOT NULL DEFAULT 'demo', address TEXT);
CREATE TABLE IF NOT EXISTS inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT NOT NULL, sku TEXT, product TEXT NOT NULL, brand TEXT,
  specs TEXT NOT NULL, price REAL NOT NULL, currency TEXT NOT NULL, stock INTEGER NOT NULL, image_file TEXT,
  updated_at TEXT);
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT NOT NULL, inventory_id INTEGER, request_id INTEGER,
  product TEXT NOT NULL, qty INTEGER NOT NULL, unit_price REAL, currency TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shopper_profiles (
  id TEXT PRIMARY KEY, city TEXT, name TEXT, device TEXT, budget REAL, currency TEXT, language TEXT,
  needs TEXT NOT NULL DEFAULT '[]', updated_at TEXT);
CREATE TABLE IF NOT EXISTS cities (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT, lat REAL, lng REAL);
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
    ("sg-harbour", "singapore", "Harbour Tech", "Bugis"),
    ("sg-lioncity", "singapore", "Lion City Mobiles", "Orchard"),
    ("sg-marina", "singapore", "Marina Gadgets", "Jurong East"),
    ("sp-paulista", "sao-paulo", "Paulista Eletrônicos", "Bela Vista"),
    ("sp-centro", "sao-paulo", "Loja Centro Tech", "Centro"),
    ("sp-vila", "sao-paulo", "Vila Digital", "Vila Mariana"),
    ("mu-seaface", "mumbai", "Seaface Electronics", "Worli"),
    ("mu-gateway", "mumbai", "Gateway Mobiles", "Andheri"),
    ("mu-metro", "mumbai", "Metro Gadget Hub", "Dadar"),
]

CHARGER_65 = {"wattage_w": 65, "connector": "USB-C", "usb_pd": True}
CHARGER_45 = {"wattage_w": 45, "connector": "USB-C", "usb_pd": True}
CABLE = {"connector": "USB-C", "max_watts": 100}
POWER_BANK = {"capacity_mah": 20000, "connector": "USB-C"}

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
    # Accessories, so multi-item baskets have real choices across shops.
    ("sg-harbour", "USB-C to USB-C cable 100W 2m", CABLE, 19, "SGD", 6),
    ("sg-harbour", "Power bank 20000mAh USB-C PD", POWER_BANK, 45, "SGD", 4),
    ("sg-lioncity", "Power bank 20000mAh USB-C", POWER_BANK, 35, "SGD", 5),
    ("sg-lioncity", "USB-C cable 100W 1m", CABLE, 12, "SGD", 10),
    ("sg-lioncity", "Travel adapter UK plug", {}, 15, "SGD", 8),
    ("sg-marina", "Travel adapter UK plug", {}, 12, "SGD", 4),
    ("sp-paulista", "Cabo USB-C 100W", CABLE, 59, "BRL", 5),
    ("sp-paulista", "Power bank 20000mAh USB-C PD", POWER_BANK, 129, "BRL", 3),
    ("sp-centro", "Cabo USB-C para USB-C 100W", CABLE, 45, "BRL", 8),
    ("sp-vila", "Power bank 20000mAh USB-C", POWER_BANK, 109, "BRL", 4),
    ("mu-seaface", "USB-C cable 100W", CABLE, 399, "INR", 5),
    ("mu-gateway", "Power bank 20000mAh USB-C PD", POWER_BANK, 1499, "INR", 3),
    ("mu-gateway", "USB-C to USB-C cable 100W", CABLE, 349, "INR", 4),
    ("mu-metro", "Power bank 20000mAh USB-C", POWER_BANK, 1299, "INR", 6),
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
            _migrate(_CONN)
            _CONN_PATH = path
            _load_cities(_CONN)
            if _CONN.execute("SELECT COUNT(*) FROM shops").fetchone()[0] == 0:
                _seed(_CONN)
        return _CONN


def _migrate(c: sqlite3.Connection) -> None:
    """Add columns introduced after the first release to an existing local database."""
    have = {r[1] for r in c.execute("PRAGMA table_info(shops)").fetchall()}
    for col, ddl in (("lat", "REAL"), ("lng", "REAL"), ("source", "TEXT NOT NULL DEFAULT 'demo'"), ("address", "TEXT"),
                     ("phone", "TEXT"), ("kind", "TEXT"), ("maps_url", "TEXT"), ("rating", "REAL"),
                     ("rating_count", "INTEGER")):
        if col not in have:
            c.execute(f"ALTER TABLE shops ADD COLUMN {col} {ddl}")
    c.execute("UPDATE shops SET name=REPLACE(name, ' (demo)', '') WHERE name LIKE '% (demo)'")
    have_resp = {r[1] for r in c.execute("PRAGMA table_info(responses)").fetchall()}
    for col in ("message", "evidence_class", "inventory_id", "photo_file"):
        if col not in have_resp:
            c.execute(f"ALTER TABLE responses ADD COLUMN {col} {'INTEGER' if col == 'inventory_id' else 'TEXT'}")
    have_req = {r[1] for r in c.execute("PRAGMA table_info(requests)").fetchall()}
    if "shopper_id" not in have_req:
        c.execute("ALTER TABLE requests ADD COLUMN shopper_id TEXT")
    for col in ("category", "ref_image"):
        if col not in have_req:
            c.execute(f"ALTER TABLE requests ADD COLUMN {col} TEXT")
    c.execute("UPDATE shops SET kind='electronics' WHERE source='demo' AND kind IS NULL")
    for shop_id, (lat, lng) in _SHOP_COORDS.items():
        c.execute("UPDATE shops SET lat=?, lng=? WHERE id=? AND lat IS NULL", (lat, lng, shop_id))
    c.commit()


def _load_cities(c: sqlite3.Connection) -> None:
    from app.commerce_loop.locale import register_city

    for row in c.execute("SELECT * FROM cities").fetchall():
        register_city(row["name"], row["country"] or "", row["lat"], row["lng"])


def save_city(city: dict) -> None:
    execute("INSERT OR REPLACE INTO cities (id, name, country, lat, lng) VALUES (?,?,?,?,?)",
            (city["id"], city["name"], city.get("country"), city.get("lat"), city.get("lng")))


def upsert_shops(city: str, shops: list[dict]) -> int:
    with _LOCK:
        c = conn()
        c.executemany(
            "INSERT INTO shops (id, city, name, area, lat, lng, source, address, phone, kind, maps_url, rating, rating_count)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET name=excluded.name, area=excluded.area, lat=excluded.lat,"
            " lng=excluded.lng, address=excluded.address, phone=COALESCE(excluded.phone, shops.phone),"
            " kind=COALESCE(excluded.kind, shops.kind), maps_url=COALESCE(excluded.maps_url, shops.maps_url),"
            " rating=COALESCE(excluded.rating, shops.rating), rating_count=COALESCE(excluded.rating_count, shops.rating_count)",
            [(x["id"], city, x["name"], x.get("area") or "", x.get("lat"), x.get("lng"), x["source"],
              x.get("address"), x.get("phone"), x.get("kind"), x.get("maps_url"), x.get("rating"),
              x.get("rating_count")) for x in shops])
        c.commit()
    return len(shops)


def reset() -> None:
    try:
        from app.commerce_loop import discovery

        discovery._CACHE.clear()
    except Exception:  # noqa: BLE001
        pass
    with _LOCK:
        c = conn()
        for table in ("shops", "listings", "requests", "responses", "demand_events", "shopper_profiles", "inventory", "sales"):
            c.execute(f"DELETE FROM {table}")
        _seed(c)


_SHOP_COORDS = {
    "sg-harbour": (1.3003, 103.8556), "sg-lioncity": (1.3048, 103.8318), "sg-marina": (1.3329, 103.7436),
    "sp-paulista": (-23.5614, -46.6559), "sp-centro": (-23.5450, -46.6340), "sp-vila": (-23.5891, -46.6349),
    "mu-seaface": (19.0176, 72.8170), "mu-gateway": (19.1197, 72.8468), "mu-metro": (19.0178, 72.8478),
}


def _seed(c: sqlite3.Connection) -> None:
    c.executemany("INSERT INTO shops (id, city, name, area, lat, lng, source, kind) VALUES (?,?,?,?,?,?,'demo','electronics')",
                  [(i, ci, n, a, *_SHOP_COORDS.get(i, (None, None))) for i, ci, n, a in SHOPS])
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
    if "充电宝" in product or ("power" in words and "bank" in words) or "powerbank" in words:
        return "power bank 20000mah"
    if ("travel" in words or "plug" in words) and ("adapter" in words or "adaptor" in words) and "charger" not in words:
        return "travel adapter"
    if any(w in words for w in ("charger", "carregador", "adapter", "adaptor", "चार्जर")) or "充电" in product or "चार्जर" in product:
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
    return rows("SELECT * FROM shops WHERE city=? ORDER BY source='demo' DESC, name", (city,))


def shop(shop_id: str) -> dict | None:
    found = rows("SELECT * FROM shops WHERE id=?", (shop_id,))
    return found[0] if found else None


def listings_for(shop_id: str) -> list[dict]:
    out = rows("SELECT * FROM listings WHERE shop_id=?", (shop_id,))
    for item in out:
        item["specs"] = json.loads(item["specs"])
    return out


def create_request(city: str, product: str, specs: dict, budget: float | None, currency: str | None,
                   language: str, raw_text: str, shopper_id: str | None = None, category: str | None = None,
                   ref_image: str | None = None) -> int:
    from app.commerce_loop.categories import category_of

    category = category or category_of(product)
    rid = execute(
        "INSERT INTO requests (city, product, specs, budget, currency, language, raw_text, status, created_at, shopper_id,"
        " category, ref_image) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (city, product, json.dumps(specs), budget, currency, language, raw_text[:500], "OPEN", now_iso(), shopper_id,
         category, ref_image))
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
    req["ref_image_url"] = ref_image_url(req.get("ref_image"))
    return req


def ref_image_url(name: str | None) -> str | None:
    return f"/api/v2/loop/media/requests/{name}" if name else None


def routing_summary(city: str) -> dict:
    """How requests were routed: per category (requests, shops reached, answered) and per shop (received by category)."""
    from app.commerce_loop.categories import shop_serves

    reqs = rows("SELECT id, category, status FROM requests WHERE city=?", (city,))
    shops = shops_in_city(city)
    replied = {(r["request_id"], r["shop_id"]) for r in rows(
        "SELECT x.request_id, x.shop_id FROM responses x JOIN requests q ON q.id=x.request_id WHERE q.city=?", (city,))}
    by_cat: dict[str, dict] = {}
    by_shop: dict[str, dict] = {s["id"]: {"received": 0, "answered": 0, "by_category": {}} for s in shops}
    for r in reqs:
        cat = r["category"] or "general"
        c = by_cat.setdefault(cat, {"category": cat, "requests": 0, "answered": 0, "shops_reached": 0})
        c["requests"] += 1
        c["answered"] += r["status"] == "ANSWERED"
        reached = [s for s in shops if shop_serves(s.get("kind"), cat)]
        c["shops_reached"] = max(c["shops_reached"], len(reached))
        for s in reached:
            b = by_shop[s["id"]]
            b["received"] += 1
            b["by_category"][cat] = b["by_category"].get(cat, 0) + 1
            b["answered"] += (r["id"], s["id"]) in replied
    return {"categories": sorted(by_cat.values(), key=lambda x: -x["requests"]), "shops": by_shop}


def shops_serving(city: str, category: str | None) -> list[dict]:
    from app.commerce_loop.categories import shop_serves

    return [s for s in shops_in_city(city) if shop_serves(s.get("kind"), category)]


def open_requests(city: str, shop_id: str | None = None) -> list[dict]:
    from app.commerce_loop.categories import shop_serves

    out = rows("SELECT * FROM requests WHERE city=? ORDER BY id DESC LIMIT 60", (city,))
    if shop_id:
        kind = (shop(shop_id) or {}).get("kind")
        out = [r for r in out if shop_serves(kind, r.get("category"))]
    out = out[:30]
    for r in out:
        r["ref_image_url"] = ref_image_url(r.get("ref_image"))
        r["specs"] = json.loads(r["specs"])
        r["responses"] = responses_for(r["id"])
        sid = r.get("shopper_id")
        r["shopper_past_requests"] = (rows("SELECT COUNT(*) AS n FROM requests WHERE shopper_id=? AND id<?",
                                           (sid, r["id"]))[0]["n"] if sid else 0)
    return out


def replace_inventory(shop_id: str, currency: str, items: list[dict]) -> None:
    """Uploaded sheet becomes the shop's inventory and its listings (what shoppers' searches see)."""
    with _LOCK:
        c = conn()
        c.execute("DELETE FROM inventory WHERE shop_id=?", (shop_id,))
        c.execute("DELETE FROM listings WHERE shop_id=?", (shop_id,))
        ts = now_iso()
        c.executemany(
            "INSERT INTO inventory (shop_id, sku, product, brand, specs, price, currency, stock, image_file, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(shop_id, i["sku"], i["product"], i["brand"], json.dumps(i["specs"]), i["price"], currency, i["stock"],
              i["image_file"], ts) for i in items])
        c.executemany("INSERT INTO listings (shop_id, product, specs, price, currency, stock) VALUES (?,?,?,?,?,?)",
                      [(shop_id, (f"{i['brand']} " if i["brand"] else "") + i["product"], json.dumps(i["specs"]),
                        i["price"], currency, i["stock"]) for i in items])
        c.commit()


def update_inventory_item(item_id: int, *, price: float | None = None, stock: int | None = None) -> dict | None:
    item = inventory_item(item_id)
    if not item:
        return None
    new_price = item["price"] if price is None else price
    new_stock = item["stock"] if stock is None else stock
    name = ((item["brand"] + " ") if item["brand"] else "") + item["product"]
    with _LOCK:
        c = conn()
        c.execute("UPDATE inventory SET price=?, stock=?, updated_at=? WHERE id=?", (new_price, new_stock, now_iso(), item_id))
        c.execute("UPDATE listings SET price=?, stock=? WHERE shop_id=? AND product=?",
                  (new_price, new_stock, item["shop_id"], name))
        c.commit()
    return inventory_item(item_id)


def record_sale(shop_id: str, inventory_id: int | None, qty: int, request_id: int | None = None,
                unit_price: float | None = None) -> dict:
    """A sale the shopkeeper confirms; reduces stock of the inventory row when there is one."""
    item = inventory_item(inventory_id) if inventory_id else None
    product = ((item["brand"] + " ") if item and item["brand"] else "") + (item["product"] if item else "item")
    price = unit_price if unit_price is not None else (item["price"] if item else None)
    sid = execute("INSERT INTO sales (shop_id, inventory_id, request_id, product, qty, unit_price, currency, created_at)"
                  " VALUES (?,?,?,?,?,?,?,?)",
                  (shop_id, inventory_id, request_id, product, qty, price, item["currency"] if item else None, now_iso()))
    if item:
        update_inventory_item(item["id"], stock=max(0, item["stock"] - qty))
    return {"sale_id": sid, "product": product, "qty": qty, "stock_left": max(0, item["stock"] - qty) if item else None}


def sales_for(shop_id: str, days: int = 56) -> list[dict]:
    return rows("SELECT * FROM sales WHERE shop_id=? AND created_at >= datetime('now', ?) ORDER BY id",
                (shop_id, f"-{days} day"))


def inventory_for(shop_id: str) -> list[dict]:
    out = rows("SELECT * FROM inventory WHERE shop_id=? ORDER BY id", (shop_id,))
    for item in out:
        item["specs"] = json.loads(item["specs"])
    return out


def inventory_item(item_id: int) -> dict | None:
    found = rows("SELECT * FROM inventory WHERE id=?", (item_id,))
    if not found:
        return None
    found[0]["specs"] = json.loads(found[0]["specs"])
    return found[0]


def get_profile(shopper_id: str) -> dict | None:
    found = rows("SELECT * FROM shopper_profiles WHERE id=?", (shopper_id,))
    if not found:
        return None
    prof = found[0]
    prof["needs"] = json.loads(prof["needs"] or "[]")
    return prof


def save_profile(shopper_id: str, city: str, name: str, *, device: str | None = None, budget: float | None = None,
                 currency: str | None = None, language: str | None = None, need: dict | None = None) -> dict:
    prof = get_profile(shopper_id) or {"id": shopper_id, "city": city, "name": name, "device": None, "budget": None,
                                       "currency": None, "language": None, "needs": []}
    prof.update({k: v for k, v in {"device": device, "budget": budget, "currency": currency,
                                   "language": language}.items() if v})
    if need and (not prof["needs"] or {k: v for k, v in prof["needs"][-1].items() if k != "at"}
                 != {k: v for k, v in need.items() if k != "at"}):
        prof["needs"] = (prof["needs"] + [need])[-8:]
    execute("INSERT OR REPLACE INTO shopper_profiles (id, city, name, device, budget, currency, language, needs, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (shopper_id, city, name, prof["device"], prof["budget"], prof["currency"], prof["language"],
             json.dumps(prof["needs"]), now_iso()))
    return prof


def forget_profile(shopper_id: str) -> None:
    execute("DELETE FROM shopper_profiles WHERE id=?", (shopper_id,))


def responses_for(request_id: int) -> list[dict]:
    out = rows("SELECT r.*, s.name AS shop_name, s.lat AS shop_lat, s.lng AS shop_lng, s.address AS shop_address,"
               " s.source AS shop_source, s.maps_url AS shop_maps_url, s.rating AS shop_rating,"
               " s.rating_count AS shop_rating_count, s.area AS shop_area,"
               " TRIM(COALESCE(i.brand || ' ', '') || i.product) AS inventory_product"
               " FROM responses r JOIN shops s ON s.id=r.shop_id LEFT JOIN inventory i ON i.id=r.inventory_id"
               " WHERE request_id=? ORDER BY r.id", (request_id,))
    for r in out:
        r["claim"] = json.loads(r["claim"])
        r["check_result"] = json.loads(r["check_result"])
        r["photo_url"] = f"/api/v2/loop/media/{r['shop_id']}/{r['photo_file']}" if r.get("photo_file") else None
    return out


def add_response(request_id: int, shop_id: str, price: float | None, currency: str | None, stock: int | None,
                 claim: dict, check: dict, status: str, *, message: str | None = None,
                 evidence_class: str | None = None, inventory_id: int | None = None,
                 photo_file: str | None = None) -> int:
    rid = execute(
        "INSERT INTO responses (request_id, shop_id, price, currency, stock, claim, check_result, status, created_at,"
        " message, evidence_class, inventory_id, photo_file) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (request_id, shop_id, price, currency, stock, json.dumps(claim), json.dumps(check), status, now_iso(),
         message, evidence_class, inventory_id, photo_file))
    if status == "PHOTO_MATCHES_REQUEST":
        execute("UPDATE requests SET status='ANSWERED' WHERE id=?", (request_id,))
        req = rows("SELECT * FROM requests WHERE id=?", (request_id,))[0]
        # Mark the demand as answered: the most recent unanswered live event for this need.
        execute("UPDATE demand_events SET answered=1 WHERE id=(SELECT id FROM demand_events WHERE city=? AND"
                " product=? AND answered=0 AND source='live_app' ORDER BY id DESC LIMIT 1)",
                (req["city"], req["product"]))
    return rid
