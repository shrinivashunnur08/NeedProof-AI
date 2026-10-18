"""Product categories: which kind of shop sells an item, and how to find such shops on the map.

Any product works. A request is mapped to a category from its words (several languages); the category picks
Google Places types and OpenStreetMap shop tags for real nearby shops, and decides which shops' inboxes
see the request (a clothing request does not go to phone-charger shops).
"""
from __future__ import annotations

import re

CATEGORIES: dict[str, dict] = {
    "electronics": {
        "label": "Electronics", "places": ["electronics_store", "cell_phone_store"],
        "osm": "electronics|mobile_phone|computer|hifi",
        "words": ["charger", "cable", "power bank", "powerbank", "adapter", "adaptor", "headphone", "earbud", "earphone",
                  "phone case", "mouse", "keyboard", "laptop", "usb", "hdmi", "speaker", "smartwatch", "carregador",
                  "cabo", "fone", "充电", "数据线", "耳机", "चार्जर", "केबल"],
    },
    "clothing": {
        "label": "Clothing", "places": ["clothing_store"], "osm": "clothes|boutique|fashion",
        "words": ["shirt", "t-shirt", "tshirt", "tee", "blouse", "dress", "jeans", "trouser", "pants", "jacket",
                  "hoodie", "sweater", "skirt", "shorts", "kurta", "saree", "sari", "lehenga", "suit", "blazer",
                  "camisa", "camiseta", "vestido", "calça", "jaqueta", "衬衫", "裙", "外套", "裤", "कमीज", "कुर्ता", "साड़ी"],
    },
    "shoes": {
        "label": "Shoes", "places": ["shoe_store"], "osm": "shoes",
        "words": ["shoe", "sneaker", "sandal", "boot", "slipper", "heels", "tênis", "sapato", "鞋", "जूते"],
    },
    "books": {
        "label": "Books & stationery", "places": ["book_store"], "osm": "books|stationery",
        "words": ["book", "novel", "textbook", "notebook", "pen", "stationery", "livro", "书", "किताब"],
    },
    "pharmacy": {
        "label": "Pharmacy", "places": ["pharmacy", "drugstore"], "osm": "chemist|pharmacy",
        "words": ["medicine", "paracetamol", "ibuprofen", "bandage", "thermometer", "sunscreen", "remédio", "药",
                  "दवा"],
    },
    "hardware": {
        "label": "Hardware", "places": ["hardware_store"], "osm": "hardware|doityourself",
        "words": ["drill", "screw", "hammer", "paint", "tool", "bulb", "extension cord", "pipe", "ferramenta", "工具"],
    },
    "home": {
        "label": "Home goods", "places": ["home_goods_store", "furniture_store"], "osm": "houseware|furniture|interior_decoration",
        "words": ["lamp", "bedsheet", "pillow", "kettle", "cookware", "pan", "curtain", "chair", "table", "mug"],
    },
    "sports": {
        "label": "Sports", "places": ["sporting_goods_store"], "osm": "sports|outdoor",
        "words": ["football", "racket", "yoga mat", "dumbbell", "bicycle", "helmet", "jersey", "badminton"],
    },
    "jewelry": {
        "label": "Jewellery", "places": ["jewelry_store"], "osm": "jewelry",
        "words": ["ring", "necklace", "bracelet", "earring", "pendant", "watch strap"],
    },
    "grocery": {
        "label": "Grocery", "places": ["grocery_store", "supermarket"], "osm": "supermarket|convenience|greengrocer",
        "words": ["rice", "milk", "bread", "eggs", "fruit", "vegetable", "spice", "flour", "oil"],
    },
}
GENERAL_PLACES = ["electronics_store", "cell_phone_store", "clothing_store", "shoe_store", "department_store",
                  "book_store", "home_goods_store", "sporting_goods_store"]
GENERAL_OSM = "electronics|mobile_phone|computer|clothes|boutique|shoes|department_store|books|houseware|sports"

_PLACES_TO_CAT = {t: c for c, v in CATEGORIES.items() for t in v["places"]}
_OSM_TO_CAT = {t: c for c, v in CATEGORIES.items() for t in v["osm"].split("|")}


def category_of(text: str | None, hint: str | None = None) -> str:
    """Best category for a product text (and an optional category hint from the intent)."""
    blob = f"{text or ''} {hint or ''}".casefold()
    best, best_pos = "general", 10**9
    for cat, spec in CATEGORIES.items():
        for w in spec["words"]:
            m = re.search(rf"(?<![a-z]){re.escape(w.casefold())}", blob)
            if m and m.start() < best_pos:
                best, best_pos = cat, m.start()
    return best


def item_noun(text: str) -> str | None:
    """The category word that names the item (e.g. 'shirt' in 'navy floral shirt size M')."""
    blob = (text or "").casefold()
    hits = []
    for spec in CATEGORIES.values():
        for w in spec["words"]:
            m = re.search(rf"(?<![a-z]){re.escape(w.casefold())}", blob)
            if m:
                hits.append((m.start(), w))
    return min(hits)[1] if hits else None


def shop_kind_from_places(types: list[str] | None, primary: str | None) -> str:
    for t in [primary, *(types or [])]:
        if t and t in _PLACES_TO_CAT:
            return _PLACES_TO_CAT[t]
    return "general"


def shop_kind_from_osm(tag: str | None) -> str:
    return _OSM_TO_CAT.get((tag or "").casefold(), "general")


def places_types(category: str) -> list[str]:
    return CATEGORIES.get(category, {}).get("places") or GENERAL_PLACES


def osm_pattern(category: str) -> str:
    return CATEGORIES.get(category, {}).get("osm") or GENERAL_OSM


def shop_serves(shop_kind: str | None, request_category: str | None) -> bool:
    """Which inboxes see a request: same category, or a general/department store, or a general request."""
    kind = shop_kind or "general"
    cat = request_category or "general"
    return kind == cat or kind == "general" or cat == "general"
