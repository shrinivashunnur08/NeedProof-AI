"""Where is the shopper, and which real shops are nearby?

Free by default: OpenStreetMap Nominatim (geocoding) and Overpass (shops).
`DISCOVERY=places` with `MAPS_API_KEY` uses Google Places API (New) Nearby Search.
Real shops are listed as businesses that may stock an item; nobody is contacted by this demo.
"""
from __future__ import annotations

import logging
import math
import time

import httpx

from app.commerce_loop import store
from app.commerce_loop.locale import CITIES, register_city
from app.commerce_loop.providers import setting

logger = logging.getLogger(__name__)

UA = {"User-Agent": "NeedProof-AI hackathon demo (github.com/shrinivashunnur08/NeedProof-AI)"}
NOMINATIM = "https://nominatim.openstreetmap.org"
OVERPASS = "https://overpass-api.de/api/interpreter"
PLACES_NEARBY = "https://places.googleapis.com/v1/places:searchNearby"
_CACHE: dict[tuple, tuple[float, dict]] = {}
_TTL = 600


class DiscoveryError(Exception):
    pass


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def _get(url: str, params: dict, timeout: float = 12) -> dict | list:
    with httpx.Client(timeout=timeout, headers=UA) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def reverse_geocode(lat: float, lng: float) -> dict:
    data = _get(f"{NOMINATIM}/reverse", {"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 16,
                                         "accept-language": "en"})
    addr = data.get("address", {}) if isinstance(data, dict) else {}
    city = (addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("state_district")
            or addr.get("county") or addr.get("state") or addr.get("country") or "Here")
    area = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or addr.get("road") or ""
    return {"city": city, "area": area, "country_code": addr.get("country_code", ""),
            "label": ", ".join(x for x in (area, city) if x)}


def geocode(query: str, near: dict | None = None) -> dict:
    params = {"format": "jsonv2", "q": query, "limit": 1, "addressdetails": 1, "accept-language": "en"}
    if near and near.get("country"):
        params["countrycodes"] = near["country"].lower()
    data = _get(f"{NOMINATIM}/search", params)
    if not data:
        raise DiscoveryError(f"Could not find '{query}'")
    hit = data[0]
    addr = hit.get("address", {})
    city = (addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("state")
            or addr.get("country") or query)
    area = addr.get("suburb") or addr.get("neighbourhood") or addr.get("road") or ""
    return {"lat": float(hit["lat"]), "lng": float(hit["lon"]), "city": city, "area": area,
            "country_code": addr.get("country_code", ""), "label": ", ".join(x for x in (area, city) if x)}


def _osm_shops(lat: float, lng: float, radius_m: int) -> list[dict]:
    query = f"""[out:json][timeout:15];
(
  node["shop"~"electronics|mobile_phone|computer|hifi"](around:{radius_m},{lat},{lng});
  way["shop"~"electronics|mobile_phone|computer|hifi"](around:{radius_m},{lat},{lng});
);
out center 40;"""
    with httpx.Client(timeout=20, headers=UA) as c:
        r = c.post(OVERPASS, data={"data": query})
        r.raise_for_status()
        elements = r.json().get("elements", [])
    shops = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name:
            continue
        la = el.get("lat") or el.get("center", {}).get("lat")
        ln = el.get("lon") or el.get("center", {}).get("lon")
        street = " ".join(x for x in (tags.get("addr:housenumber"), tags.get("addr:street")) if x)
        shops.append({"id": f"osm-{el['type'][0]}{el['id']}", "name": name, "lat": la, "lng": ln,
                      "area": tags.get("addr:suburb") or tags.get("addr:street") or tags.get("shop", "").replace("_", " "),
                      "address": street or None, "source": "openstreetmap"})
    return shops


def _google_shops(lat: float, lng: float, radius_m: int) -> list[dict]:
    key = setting("MAPS_API_KEY")
    if not key:
        raise DiscoveryError("MAPS_API_KEY is not set")
    body = {"includedTypes": ["electronics_store", "cell_phone_store"], "maxResultCount": 20,
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": float(radius_m)}}}
    headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location"}
    with httpx.Client(timeout=15) as c:
        r = c.post(PLACES_NEARBY, json=body, headers=headers)
        r.raise_for_status()
        places = r.json().get("places", [])
    return [{"id": f"gpl-{p['id']}", "name": p.get("displayName", {}).get("text", "Shop"),
             "lat": p.get("location", {}).get("latitude"), "lng": p.get("location", {}).get("longitude"),
             "area": (p.get("formattedAddress") or "").split(",")[0], "address": p.get("formattedAddress"),
             "source": "google_places"} for p in places]


def nearby_shops(lat: float, lng: float, radius_m: int = 2500) -> tuple[list[dict], str]:
    mode = setting("DISCOVERY", "osm").lower()
    if mode == "places":
        try:
            return _google_shops(lat, lng, radius_m), "google_places"
        except Exception as exc:  # noqa: BLE001 - fall back to the free source
            logger.warning("Google Places failed (%s); using OpenStreetMap", type(exc).__name__)
    return _osm_shops(lat, lng, radius_m), "openstreetmap"


def locate(lat: float | None = None, lng: float | None = None, query: str | None = None,
           near_city: str | None = None, with_shops: bool = True) -> dict:
    """Resolve a position or a typed place, register its city, and load real shops nearby."""
    if setting("DISCOVERY", "osm").lower() == "off":
        raise DiscoveryError("Real shop discovery is turned off (DISCOVERY=off)")
    key = (round(lat, 3) if lat is not None else None, round(lng, 3) if lng is not None else None,
           (query or "").casefold(), near_city)
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < _TTL:
        return cached[1]
    if query:
        place = geocode(query, CITIES.get(near_city or ""))
        lat, lng = place["lat"], place["lng"]
    elif lat is not None and lng is not None:
        place = reverse_geocode(lat, lng)
    else:
        raise DiscoveryError("Give a position or a place name")
    city = register_city(place["city"], place["country_code"], lat, lng)
    store.conn()
    store.save_city(city)
    shops, source = ([], "none")
    if with_shops:
        try:
            shops, source = nearby_shops(lat, lng)
            store.upsert_shops(city["id"], shops)
        except Exception as exc:  # noqa: BLE001 - location still useful without shops
            logger.warning("Shop discovery failed (%s)", type(exc).__name__)
            source = f"unavailable ({type(exc).__name__})"
    for s in shops:
        if s.get("lat") is not None:
            s["distance_km"] = haversine_km(lat, lng, s["lat"], s["lng"])
    shops.sort(key=lambda s: s.get("distance_km", 99))
    result = {"city": city, "label": place["label"] or city["name"], "lat": lat, "lng": lng,
              "shops_found": len(shops), "source": source, "nearest": shops[:5],
              "note": "Real businesses from public map data. This demo never contacts them."}
    _CACHE[key] = (time.time(), result)
    return result
