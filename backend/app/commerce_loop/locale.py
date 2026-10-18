"""Currency and city helpers so the loop works in any market, not only INR."""
from __future__ import annotations

import re
from dataclasses import dataclass

CITIES = {
    "singapore": {"id": "singapore", "name": "Singapore", "country": "SG", "currency": "SGD",
                  "symbol": "S$", "languages": ["en", "zh", "ms", "ta"], "tz": "Asia/Singapore"},
    "sao-paulo": {"id": "sao-paulo", "name": "São Paulo", "country": "BR", "currency": "BRL",
                  "symbol": "R$", "languages": ["pt"], "tz": "America/Sao_Paulo"},
    "mumbai": {"id": "mumbai", "name": "Mumbai", "country": "IN", "currency": "INR",
               "symbol": "₹", "languages": ["hi", "mr", "en"], "tz": "Asia/Kolkata"},
}

# Currency by ISO country code for cities discovered at runtime (fallback USD).
COUNTRY_CURRENCY = {
    "sg": "SGD", "br": "BRL", "in": "INR", "us": "USD", "gb": "GBP", "my": "MYR", "id": "IDR", "th": "THB",
    "ph": "PHP", "vn": "VND", "jp": "JPY", "kr": "KRW", "cn": "CNY", "hk": "HKD", "tw": "TWD", "au": "AUD",
    "nz": "NZD", "ae": "AED", "sa": "SAR", "de": "EUR", "fr": "EUR", "es": "EUR", "it": "EUR", "nl": "EUR",
    "ie": "EUR", "pt": "EUR", "ca": "CAD", "mx": "MXN", "za": "ZAR", "ng": "NGN", "ke": "KES", "eg": "EGP",
}
CITY_CENTERS = {"singapore": (1.2966, 103.8520), "sao-paulo": (-23.5613, -46.6565), "mumbai": (19.0176, 72.8562)}
for _cid, (_lat, _lng) in CITY_CENTERS.items():
    CITIES[_cid].update({"lat": _lat, "lng": _lng, "demo": True})


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:40] or "here"


def register_city(name: str, country_code: str, lat: float, lng: float) -> dict:
    """Add a real city discovered from the shopper's location (kept in memory and in the store)."""
    for city in CITIES.values():
        if city["name"].casefold() == name.casefold() or slug(city["name"]) == slug(name):
            return city
    cc = (country_code or "").lower()
    currency = COUNTRY_CURRENCY.get(cc, "USD")
    city = {"id": slug(name), "name": name, "country": cc.upper(), "currency": currency,
            "symbol": SYMBOLS.get(currency, currency + " "), "languages": [], "tz": "", "lat": lat, "lng": lng,
            "demo": False}
    CITIES[city["id"]] = city
    return city


CITY_ALIASES = {
    "singapore": "singapore", "sg": "singapore", "新加坡": "singapore", "singapura": "singapore",
    "சிங்கப்பூர்": "singapore",
    "são paulo": "sao-paulo", "sao paulo": "sao-paulo", "sp": "sao-paulo", "sampa": "sao-paulo",
    "mumbai": "mumbai", "bombay": "mumbai", "मुंबई": "mumbai", "thane": "mumbai", "ठाणे": "mumbai",
}

# Longest tokens first so "S$" wins over "$" and "R$" over "$".
_CURRENCY_TOKENS = [
    ("US$", "USD"), ("S$", "SGD"), ("R$", "BRL"), ("RM", "MYR"), ("MYR", "MYR"), ("A$", "AUD"), ("HK$", "HKD"), ("SGD", "SGD"), ("BRL", "BRL"), ("INR", "INR"),
    ("USD", "USD"), ("GBP", "GBP"), ("EUR", "EUR"), ("JPY", "JPY"), ("Rs.", "INR"), ("Rs", "INR"),
    ("₹", "INR"), ("£", "GBP"), ("€", "EUR"), ("¥", "JPY"), ("元", "SGD"), ("新币", "SGD"),
    ("reais", "BRL"), ("real", "BRL"), ("rupees", "INR"), ("रुपये", "INR"), ("रुपए", "INR"),
    ("dollars", "USD"), ("$", "USD"),
]
SYMBOLS = {"SGD": "S$", "BRL": "R$", "INR": "₹", "USD": "US$", "GBP": "£", "EUR": "€", "JPY": "¥", "MYR": "RM",
           "AUD": "A$", "IDR": "Rp", "THB": "฿", "PHP": "₱", "HKD": "HK$", "AED": "AED ", "CAD": "C$"}

_NUM = r"(\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d{1,2})?)\s*(k|K|mil|thousand|हजार|千)?"


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    def format(self) -> str:
        sym = SYMBOLS.get(self.currency, self.currency + " ")
        value = f"{self.amount:,.0f}" if self.amount == int(self.amount) else f"{self.amount:,.2f}"
        return f"{sym}{value}"


def resolve_city(text: str | None) -> str | None:
    if not text:
        return None
    low = text.casefold().strip()
    if low in CITIES:
        return low
    for alias, city in sorted(CITY_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in low:
            return city
    return None


def _to_number(raw: str, multiplier: str | None) -> float:
    s = raw.replace(" ", "")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        s = re.sub(r"[.,]", "", s)
    else:
        s = s.replace(",", ".")
    value = float(s)
    if multiplier and multiplier.lower() in {"k", "mil", "thousand", "हजार", "千"}:
        value *= 1000
    return value


def parse_money(text: str, default_currency: str | None = None) -> Money | None:
    """Find a budget like 'under S$60', 'até R$ 250', '₹1,000', '1k rupees'."""
    if not text:
        return None
    for token, code in _CURRENCY_TOKENS:
        t = re.escape(token)
        pattern = rf"(?:{t})\s*{_NUM}|{_NUM}\s*(?:{t})"
        flags = re.IGNORECASE if token.isalpha() else 0
        if token.isalpha():
            pattern = rf"(?:(?<![A-Za-z]){t}(?![A-Za-z]))\s*{_NUM}|{_NUM}\s*(?:(?<![A-Za-z]){t}(?![A-Za-z]))"
        m = re.search(pattern, text, flags)
        if m:
            g = m.groups()
            raw, mult = (g[0], g[1]) if g[0] else (g[2], g[3])
            return Money(_to_number(raw, mult), code)
    if default_currency:
        m = re.search(rf"(?:under|below|within|max|budget|até|abaixo de|menos de|以内|以下|से कम|तक)\s*{_NUM}", text, re.IGNORECASE)
        if m:
            return Money(_to_number(m.group(1), m.group(2)), default_currency)
    return None


def engine_units(amount: float) -> int:
    """The 17C engine takes integer units in [100, 100000]; use cents when they fit.

    Budget and price always use the same scale, so comparisons stay exact.
    """
    cents = int(round(amount * 100))
    if 100 <= cents <= 100_000:
        return cents
    return max(100, min(100_000, int(round(amount))))


def engine_scale(budget: float, price: float) -> tuple[int, int]:
    cents_ok = 100 <= round(budget * 100) <= 100_000 and 1 <= round(price * 100) <= 100_000
    if cents_ok:
        return int(round(budget * 100)), int(round(price * 100))
    return max(100, min(100_000, int(round(budget)))), max(1, min(100_000, int(round(price))))
