"""Commerce loop tests. Gemini runs in mock mode, so no network or spend."""
import pytest
from pathlib import Path

PHOTOS = Path(__file__).resolve().parents[2] / "demo" / "sample_photos"
from fastapi.testclient import TestClient

from app.commerce_loop import store
from app.commerce_loop.locale import Money, engine_scale, parse_money, resolve_city
from app.commerce_loop.providers import get_providers
from app.commerce_loop.vision import PhotoClaim, check_photo


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOP_DB_PATH", str(tmp_path / "loop.db"))
    monkeypatch.setenv("GEMINI_BACKEND", "mock")
    monkeypatch.setenv("DISCOVERY", "off")  # no network in tests
    monkeypatch.delenv("COMMERCE_LOOP_ENABLED", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    yield


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.parametrize("text,amount,currency", [
    ("need a 65W charger under S$60 today", 60, "SGD"),
    ("carregador 65W até R$ 250", 250, "BRL"),
    ("65W charger ₹1,000 tak", 1000, "INR"),
    ("charger under 1k rupees", 1000, "INR"),
    ("65W 充电器 60新币以内", 60, "SGD"),
    ("charger below £40", 40, "GBP"),
    ("charger under US$45", 45, "USD"),
])
def test_parse_money_any_currency(text, amount, currency):
    m = parse_money(text)
    assert m == Money(amount, currency)


def test_parse_money_uses_city_currency_for_bare_numbers():
    assert parse_money("65W charger under 60", "SGD") == Money(60, "SGD")


def test_resolve_city_in_any_script():
    assert resolve_city("新加坡") == "singapore"
    assert resolve_city("São Paulo") == "sao-paulo"
    assert resolve_city("ठाणे") == "mumbai"
    assert resolve_city("Atlantis") is None


def test_engine_scale_keeps_budget_and_price_comparable():
    assert engine_scale(60, 49) == (6000, 4900)
    assert engine_scale(1000, 899) == (100000, 89900)
    b, p = engine_scale(5000, 4200)
    assert b > p


def test_providers_default_to_mock_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_BACKEND", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("app.commerce_loop.providers._dotenv_value", lambda name: "")
    assert get_providers().gemini_backend == "mock"
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert get_providers().gemini_backend == "ai_studio"


def test_status_reports_providers(client):
    body = client.get("/api/v2/loop/status").json()
    assert body["providers"]["gemini"]["backend"] == "mock"
    assert {c["id"] for c in body["cities"]} == {"singapore", "sao-paulo", "mumbai"}


def test_agent_finds_offers_and_asks_shops(client):
    r = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore",
        "history": [{"role": "user", "text": "I need a 65W USB-C PD charger under S$60 today"}]})
    assert r.status_code == 200
    body = r.json()
    tools = [t["tool"] for t in body["trace"]]
    assert tools[0] == "extract_intent" and "find_offers" in tools and "ask_nearby_shops" in tools
    assert body["intent"]["wattage_w"] == 65 and body["intent"]["budget_amount"] == 60
    assert body["intent"]["budget_currency"] == "SGD" and body["intent"]["urgency"] == "today"
    shops = {o["shop"]: o for o in body["offers"]}
    assert shops["Harbour Tech"]["usable"] is True
    assert shops["Lion City Mobiles"]["usable"] is False  # listed but out of stock
    marina = shops["Marina Gadgets"]
    assert marina["usable"] is False and "below the required 65W" in marina["spec_check"]["issues"][0]
    for o in body["offers"]:
        assert o["decision"]["purchase_allowed"] is False
        assert o["decision"]["workflow_state"] in {"PROVISIONAL_VERIFICATION_NEEDED", "MORE_EVIDENCE_NEEDED"}
    assert body["request"]["shops_notified"] == 3


def test_agent_asks_clarifying_question_when_item_unclear(client):
    body = client.post("/api/v2/loop/agent/chat", json={
        "city": "mumbai", "history": [{"role": "user", "text": "I need something for my laptop"}]}).json()
    assert body["request"] is None and "?" in body["reply"]


def test_shop_photo_reply_matches_and_answers_request(client):
    chat = client.post("/api/v2/loop/agent/chat", json={
        "city": "sao-paulo", "history": [{"role": "user", "text": "carregador 65W USB-C PD até R$ 250"}]}).json()
    rid = chat["request"]["id"]
    r = client.post(f"/api/v2/loop/requests/{rid}/reply", json={"shop_id": "sp-paulista", "price": 189, "stock": 2,
                                                             "mock_hint": {"product_category": "laptop charger"}})
    assert r.status_code == 200 and r.json()["check"]["status"] == "PHOTO_MATCHES_REQUEST"
    req = client.get(f"/api/v2/loop/requests/{rid}").json()
    assert req["status"] == "ANSWERED" and req["responses"][0]["shop_name"].startswith("Paulista")
    # The agent now reports the shop as photo-verified.
    again = client.post("/api/v2/loop/agent/chat", json={
        "city": "sao-paulo", "history": [{"role": "user", "text": "carregador 65W USB-C PD até R$ 250"}]}).json()
    paulista = next(o for o in again["offers"] if o["shop_id"] == "sp-paulista")
    assert paulista["photo_proof"] == "PHOTO_MATCHES_REQUEST"


def test_shop_photo_with_wrong_wattage_is_flagged(client):
    rid = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C charger under S$60"}]}).json()["request"]["id"]
    body = client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "sg-marina", "price": 29, "mock_hint": {"wattage_w": 45}}).json()
    assert body["check"]["status"] == "PHOTO_CONFLICTS_WITH_REQUEST"
    assert any("45W" in i for i in body["check"]["issues"])


def test_shop_cannot_reply_to_other_city(client):
    rid = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C charger under S$60"}]}).json()["request"]["id"]
    assert client.post(f"/api/v2/loop/requests/{rid}/reply", json={"shop_id": "mu-metro"}).status_code == 403


def test_reply_rejects_bad_image_type(client):
    rid = client.post("/api/v2/loop/agent/chat", json={
        "city": "mumbai", "history": [{"role": "user", "text": "65W USB-C charger under ₹1000"}]}).json()["request"]["id"]
    r = client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "mu-metro", "image_base64": "aGVsbG8=", "image_mime": "application/pdf"})
    assert r.status_code == 415


def test_reply_without_photo_or_model_never_matches(client):
    rid = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C charger under S$60"}]}).json()["request"]["id"]
    no_photo = client.post(f"/api/v2/loop/requests/{rid}/reply", json={"shop_id": "sg-harbour", "price": 49}).json()
    assert no_photo["check"]["status"] == "PHOTO_NOT_CHECKED"
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    unread = client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "sg-lioncity", "image_base64": png, "image_mime": "image/png"}).json()
    assert unread["check"]["status"] == "PHOTO_NOT_CHECKED"
    assert client.get(f"/api/v2/loop/requests/{rid}").json()["status"] == "OPEN"


def test_wrong_item_type_is_rejected_even_if_watts_are_higher():
    req = {"product": "65W USB-C PD charger", "specs": {"wattage_w": 65}, "budget": 60}
    mixer = PhotoClaim(is_product_photo=True, product_category="mixer grinder", wattage_w=750, is_requested_item_type=False)
    out = check_photo(req, mixer, 49)
    assert out["status"] == "PHOTO_CONFLICTS_WITH_REQUEST" and "mixer grinder" in out["issues"][0]
    sneaky = PhotoClaim(is_product_photo=True, product_category="mixer grinder", wattage_w=750, is_requested_item_type=True)
    assert check_photo(req, sneaky, 49)["status"] == "PHOTO_CONFLICTS_WITH_REQUEST"


def test_not_visible_details_are_cautions_not_conflicts():
    req = {"product": "65W USB-C PD charger", "specs": {"wattage_w": 65, "connector": "USB-C"}, "budget": 60}
    generic = PhotoClaim(is_product_photo=True, product_category="laptop charger", is_requested_item_type=True,
                         wattage_w=65, connector="USB-C",
                         concerns=["missing brand name", "missing safety marks", "missing model number"])
    out = check_photo(req, generic, 40)
    assert out["status"] == "PHOTO_MATCHES_REQUEST"
    assert len(out["cautions"]) >= 3 and not out["issues"]
    fake = PhotoClaim(is_product_photo=True, product_category="charger", wattage_w=65, connector="USB-C",
                      concerns=["Brand printed as 'Appel'"])
    assert check_photo(req, fake, 40)["status"] == "PHOTO_CONFLICTS_WITH_REQUEST"


def test_check_photo_rules():
    req = {"specs": {"wattage_w": 65, "connector": "USB-C", "usb_pd": True}, "budget": 60}
    ok = check_photo(req, PhotoClaim(is_product_photo=True, wattage_w=65, connector="USB-C", usb_pd=True), 49)
    assert ok["status"] == "PHOTO_MATCHES_REQUEST"
    unclear = check_photo(req, PhotoClaim(is_product_photo=True, connector="USB-C", usb_pd=True), 49)
    assert unclear["status"] == "PHOTO_NEEDS_CLEARER_DETAIL"
    pricey = check_photo(req, PhotoClaim(is_product_photo=True, wattage_w=65, connector="USB-C"), 75)
    assert pricey["status"] == "PHOTO_CONFLICTS_WITH_REQUEST"
    fake = check_photo(req, PhotoClaim(is_product_photo=True, wattage_w=65, concerns=["Misspelled brand"]), 49)
    assert fake["status"] == "PHOTO_CONFLICTS_WITH_REQUEST"
    assert check_photo(req, PhotoClaim(is_product_photo=False), 49)["status"] == "PHOTO_UNREADABLE"


def test_insights_and_brief(client):
    client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C PD charger under S$60"}]})
    data = client.get("/api/v2/loop/cities/singapore/insights").json()
    top = data["products"][0]
    assert top["product_key"] == "65w usb-c pd charger" and top["unmet"] > 0
    assert len(top["daily_series"]) == 28 and top["live_asks"] >= 1
    brief = client.post("/api/v2/loop/cities/singapore/brief", json={"language": "en"}).json()
    assert brief["brief"]["headline"] and len(brief["brief"]["actions"]) == 4
    assert "bundle" in brief["brief"]["actions"][-1] and brief["shop_facts"]["forecast_model"]


def test_disabled_in_production_unless_enabled(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert client.get("/api/v2/loop/status").status_code == 503
    monkeypatch.setenv("COMMERCE_LOOP_ENABLED", "true")
    assert client.get("/api/v2/loop/status").status_code == 200


def test_reset_restores_seed(client):
    client.post("/api/v2/loop/agent/chat", json={
        "city": "mumbai", "history": [{"role": "user", "text": "65W USB-C charger under ₹1000"}]})
    assert store.rows("SELECT COUNT(*) AS n FROM requests")[0]["n"] == 1
    client.post("/api/v2/loop/demo/reset")
    assert store.rows("SELECT COUNT(*) AS n FROM requests")[0]["n"] == 0


def test_city_version_changes_on_request_and_reply(client):
    from app.commerce_loop.api import _city_version
    v0 = _city_version("singapore")
    rid = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C charger under S$60"}]}).json()["request"]["id"]
    v1 = _city_version("singapore")
    assert v1 != v0
    client.post(f"/api/v2/loop/requests/{rid}/reply", json={"shop_id": "sg-harbour", "mock_hint": {}})
    assert _city_version("singapore") != v1
    assert _city_version("mumbai") == "0-0-0"


def test_vague_charger_request_gets_a_follow_up_question(client):
    body = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "I need a laptop charger today"}]}).json()
    assert body["mode"] == "clarify" and body["request"] is None
    assert "wattage" in body["intent"]["missing_info"]


def test_locate_registers_real_city_and_shops(client, monkeypatch):
    from app.commerce_loop import discovery
    monkeypatch.setenv("DISCOVERY", "osm")
    discovery._CACHE.clear()
    monkeypatch.setattr(discovery, "reverse_geocode", lambda lat, lng: {
        "city": "Kuala Lumpur", "area": "Bukit Bintang", "country_code": "my", "label": "Bukit Bintang, Kuala Lumpur"})
    monkeypatch.setattr(discovery, "nearby_shops", lambda lat, lng, radius_m=2500, category="general": ([
        {"id": "osm-n1", "name": "Plaza Gadget", "lat": 3.1466, "lng": 101.7110, "area": "Jalan Bukit Bintang",
         "address": None, "source": "openstreetmap"},
        {"id": "osm-n2", "name": "Low Yat Mobile", "lat": 3.1440, "lng": 101.7100, "area": "", "address": None,
         "source": "openstreetmap"}], "openstreetmap"))
    loc = client.post("/api/v2/loop/locate", json={"lat": 3.1478, "lng": 101.7130}).json()
    assert loc["city"]["id"] == "kuala-lumpur" and loc["city"]["currency"] == "MYR" and loc["shops_found"] == 2
    assert loc["nearest"][0]["distance_km"] < 1
    body = client.post("/api/v2/loop/agent/chat", json={
        "city": "kuala-lumpur", "lat": 3.1478, "lng": 101.7130,
        "history": [{"role": "user", "text": "65W USB-C PD charger under RM150"}]}).json()
    assert {n["shop"] for n in body["nearby"]} == {"Plaza Gadget", "Low Yat Mobile"}
    assert body["request"]["shops_notified"] == 2
    shops = client.get("/api/v2/loop/cities/kuala-lumpur/shops").json()
    assert all(s["source"] == "openstreetmap" for s in shops)


def test_shop_analytics_uses_14b_engines(client):
    a = client.get("/api/v2/loop/cities/singapore/analytics").json()
    assert a["currency"] == "SGD" and len(a["forecast"]["models"]) >= 3
    assert a["forecast"]["selected_model"] and len(a["forecast"]["daily"]) == 7
    assert a["inventory"]["status"] and a["segments"]["items"]
    assert any(r["if_bought"].startswith("65W") for r in a["baskets"]["rules"])


def test_profile_remembers_and_forgets(client):
    sid = "test-shopper-1"
    first = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "shopper_id": sid, "shopper_name": "Mei",
        "history": [{"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()
    assert first["profile"]["needs"][-1]["wattage_w"] == 65
    assert first["addon"] and "cable" in first["addon"]["item"].lower()
    # A vague follow-up a week later is filled from the profile instead of asking again.
    again = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "shopper_id": sid,
        "history": [{"role": "user", "text": "I need a laptop charger again"}]}).json()
    assert again["mode"] != "clarify" and again["intent"]["wattage_w"] == 65
    assert any("65W" in r for r in again["remembered"])
    reqs = client.get("/api/v2/loop/cities/singapore/requests").json()
    assert reqs[0]["shopper_past_requests"] >= 1
    assert client.delete(f"/api/v2/loop/shoppers/{sid}").json()["forgotten"]
    assert client.get(f"/api/v2/loop/shoppers/{sid}").json()["profile"] is None
    fresh = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "shopper_id": sid,
        "history": [{"role": "user", "text": "I need a laptop charger"}]}).json()
    assert fresh["mode"] == "clarify" and fresh["remembered"] == []


def _new_request(client, text="65W USB-C PD charger under S$60"):
    body = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": text}]}).json()
    return body["request"]["id"]


def test_inventory_sample_draft_and_approved_reply(client, monkeypatch, tmp_path):
    up = client.post("/api/v2/loop/shops/sg-marina/inventory/sample").json()
    assert up["items"] == 5 and up["with_photo"] == 3
    inv = client.get("/api/v2/loop/shops/sg-marina/inventory").json()
    assert inv[0]["image_url"] and client.get(inv[0]["image_url"]).status_code == 200
    rid = _new_request(client)
    draft = client.get(f"/api/v2/loop/requests/{rid}/draft", params={"shop_id": "sg-marina"}).json()
    assert draft["needs_human_approval"] and draft["draft"]["product"].startswith("65W")
    assert all("mixer" not in c["product"].lower() for c in draft["candidates"])
    assert draft["candidates"][0]["inventory_id"] == draft["draft"]["inventory_id"]
    # Unapproved drafts are refused.
    refused = client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "sg-marina", "inventory_id": draft["draft"]["inventory_id"], "approved_by_shopkeeper": False})
    assert refused.status_code == 409
    sent = client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "sg-marina", "inventory_id": draft["draft"]["inventory_id"], "price": 49, "stock": 7,
        "message": draft["draft"]["message"]}).json()
    # Mock model cannot read photos, so a catalog photo is never auto-verified.
    assert sent["check"]["status"] == "PHOTO_NOT_CHECKED"
    assert sent["evidence_class"] == "SHOP_CATALOG_PHOTO_READ_BY_AI"
    req = client.get(f"/api/v2/loop/requests/{rid}").json()
    assert req["responses"][-1]["message"].startswith("Yes, we have")
    # The upload also replaces what shopper searches see for that shop.
    offers = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()["offers"]
    assert any(o["shop_id"] == "sg-marina" and "VoltPro" in o["listing"] for o in offers)
    assert not any("adapter" in o["listing"].lower() for o in offers)


def test_inventory_xlsx_upload_maps_headers(client):
    import base64
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Item name", "Make", "Qty", "Selling price", "Image"])
    ws.append(["Anker 65W USB-C PD charger", "Anker", 4, "S$52", "x.jpg"])
    ws.append(["", "", "", "", ""])
    ws.append(["Mixer grinder 750W", "Philips", 2, 89, ""])
    buf = io.BytesIO()
    wb.save(buf)
    res = client.post("/api/v2/loop/shops/sg-harbour/inventory", json={
        "filename": "stock.xlsx", "sheet_base64": base64.b64encode(buf.getvalue()).decode()}).json()
    assert res["items"] == 2 and res["columns"]["price"] == "Selling price" and res["columns"]["stock"] == "Qty"
    assert any("x.jpg" in p for p in res["problems"])
    inv = client.get("/api/v2/loop/shops/sg-harbour/inventory").json()
    assert inv[0]["specs"]["wattage_w"] == 65 and inv[0]["price"] == 52 and inv[0]["stock"] == 4
    rid = _new_request(client)
    draft = client.get(f"/api/v2/loop/requests/{rid}/draft", params={"shop_id": "sg-harbour"}).json()
    assert draft["draft"]["product"].startswith("Anker") and len(draft["candidates"]) == 1
    assert any("photo" in c.lower() for c in draft["draft"]["caveats"])
    bad = client.post("/api/v2/loop/shops/sg-harbour/inventory", json={
        "filename": "x.csv", "sheet_base64": base64.b64encode(b"foo,bar\n1,2\n").decode()})
    assert bad.status_code == 422
    assert client.get("/api/v2/loop/inventory/template.xlsx").status_code == 200
    assert client.get("/api/v2/loop/media/sg-harbour/..%2F..%2Fsecret").status_code == 404


def test_draft_never_offers_wrong_item_or_spec(client):
    client.post("/api/v2/loop/shops/sg-marina/inventory/sample")
    for text in ("100W USB-C charger under S$120", "mixer grinder under S$100"):
        body = client.post("/api/v2/loop/agent/chat", json={
            "city": "singapore", "history": [{"role": "user", "text": text}]}).json()
        rid = body["request"]["id"] if body.get("request") else None
        if rid is None:
            from app.commerce_loop import store
            rid = store.create_request("singapore", text, {}, None, "SGD", "en", text)
        d = client.get(f"/api/v2/loop/requests/{rid}/draft", params={"shop_id": "sg-marina"}).json()
        assert d["draft"] is None, (text, d)


def test_bigquery_endpoints_explain_when_not_configured(client, monkeypatch):
    monkeypatch.setenv("ANALYTICS_BACKEND", "local")
    r = client.get("/api/v2/loop/cities/singapore/bigquery/forecast")
    assert r.status_code == 409 and "ANALYTICS_BACKEND=bigquery" in r.json()["detail"]
    assert client.post("/api/v2/loop/analytics/bigquery/sync").status_code == 409


def test_rate_limit_and_daily_cap(client, monkeypatch):
    from app.commerce_loop import guard
    monkeypatch.setenv("LOOP_RATE_LIMIT", "true")
    monkeypatch.setenv("LOOP_RATE_PER_MIN", "2")
    monkeypatch.setenv("LOOP_DAILY_AI_CAP", "3")
    guard.reset()
    body = {"city": "singapore", "history": [{"role": "user", "text": "I need a laptop charger"}]}
    assert client.post("/api/v2/loop/agent/chat", json=body).status_code == 200
    assert client.post("/api/v2/loop/agent/chat", json=body).status_code == 200
    assert client.post("/api/v2/loop/agent/chat", json=body).status_code == 429  # per-minute
    other = {"X-Forwarded-For": "203.0.113.9"}
    assert client.post("/api/v2/loop/agent/chat", json=body, headers=other).status_code == 200
    r = client.post("/api/v2/loop/agent/chat", json=body, headers={"X-Forwarded-For": "203.0.113.10"})
    assert r.status_code == 429 and "today" in r.json()["detail"]  # daily cap of 3
    assert client.get("/api/v2/loop/status").json()["limits"]["ai_calls_today"] == 3
    guard.reset()


def test_photo_proof_is_per_product_not_per_shop(client):
    client.post("/api/v2/loop/shops/sg-marina/inventory/sample")
    rid = _new_request(client)
    d = client.get(f"/api/v2/loop/requests/{rid}/draft", params={"shop_id": "sg-marina"}).json()
    client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "sg-marina", "inventory_id": d["draft"]["inventory_id"], "price": 49, "stock": 7,
        "mock_hint": {"wattage_w": 65}})
    offers = client.post("/api/v2/loop/agent/chat", json={
        "city": "singapore", "history": [{"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()["offers"]
    marina = {o["listing"]: o["photo_proof"] for o in offers if o["shop_id"] == "sg-marina"}
    assert marina["VoltPro 65W USB-C PD laptop charger"] == "PHOTO_MATCHES_REQUEST"
    assert marina["VoltPro 45W USB-C PD charger"] == "NONE"
    resp = client.get(f"/api/v2/loop/requests/{rid}").json()["responses"][-1]
    assert resp["inventory_product"] == "VoltPro 65W USB-C PD laptop charger"


def test_trust_report(client):
    t = client.get("/api/v2/loop/trust").json()
    assert len(t["pipeline"]) == 7 and len(t["safeguards"]) >= 10
    assert t["evals"] and all(x["passed"] == x["total"] for e in t["evals"] for x in e["tasks"])
    assert "EVSI_ONE_STEP" in t["benchmarks"]["evidence"]
    assert t["live"]["requests"] == 0


def test_my_shop_dashboard_from_live_data(client):
    client.post("/api/v2/loop/shops/sg-marina/inventory/sample")
    # 1) a charger request Marina can serve -> answered after an approved draft
    rid = _new_request(client)
    d = client.get(f"/api/v2/loop/requests/{rid}/draft", params={"shop_id": "sg-marina"}).json()
    client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "sg-marina", "inventory_id": d["draft"]["inventory_id"], "price": 49, "stock": 7})
    # 2) a request Marina could serve but did not answer -> missed
    _new_request(client, "power bank 20000mAh under S$50")
    # 3) something Marina does not stock -> missed sales
    from app.commerce_loop import store
    store.create_request("singapore", "100W USB-C charger", {"wattage_w": 100}, 120, "SGD", "en", "100W charger")
    sale = client.post("/api/v2/loop/shops/sg-marina/sales", json={
        "inventory_id": d["draft"]["inventory_id"], "request_id": rid, "qty": 2}).json()
    assert sale["stock_left"] == 5
    dash = client.get("/api/v2/loop/shops/sg-marina/dashboard").json()
    k = dash["kpis"]
    assert k["requests_reached"] == 3 and k["answered"] == 1 and k["units_sold"] == 2
    assert dash["outcomes"]["missed"] == 1 and dash["outcomes"]["not_stocked"] == 1
    assert dash["missed_sales"][0]["product"].startswith("100W")
    charger = next(i for i in dash["inventory"] if i["sku"] == "VP-65C")
    assert charger["stock"] == 5 and charger["sold"] == 2 and charger["asks"] >= 1
    edited = client.post(f"/api/v2/loop/shops/sg-marina/inventory/{charger['id']}", json={"price": 45}).json()
    assert edited["price"] == 45
    offers = client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()["offers"]
    assert any(o["shop_id"] == "sg-marina" and o["price"] == "S$45" for o in offers)
    brief = client.post("/api/v2/loop/shops/sg-marina/brief", json={"language": "en"}).json()
    assert any("100W" in a for a in brief["brief"]["actions"])
    a = client.get("/api/v2/loop/cities/singapore/analytics", params={"shop_id": "sg-marina"}).json()
    assert a["confirmed_sales_today"] == 2 and a["inventory"]["on_hand"] == 5


def test_basket_plan_across_shops(client):
    r = client.post("/api/v2/loop/basket/plan", json={
        "city": "singapore", "items": ["65W USB-C PD charger", "USB-C cable", "power bank 20000mAh"],
        "budget": 120, "max_shops": 2}).json()
    assert r["status"] == "OPTIMAL" and len(r["lines"]) == 3 and len(r["shops"]) <= 2
    # Harbour is the only in-stock 65W charger; Lion City has the cheapest cable and power bank.
    assert {ln["shop"] for ln in r["lines"]} == {"Harbour Tech", "Lion City Mobiles"}
    assert r["total"] == "S$96" and r["within_budget"] is True
    assert r["baselines"]["cheapest_item_first"]["total"] == "S$96"
    one = client.post("/api/v2/loop/basket/plan", json={
        "city": "singapore", "items": ["65W USB-C PD charger", "USB-C cable", "power bank"], "max_shops": 1}).json()
    assert one["status"] == "OPTIMAL" and one["shops"][0]["shop"] == "Harbour Tech" and one["total"] == "S$113"
    tight = client.post("/api/v2/loop/basket/plan", json={
        "city": "singapore", "items": ["65W charger", "power bank"], "budget": 50}).json()
    assert tight["status"] == "NO_PLAN_WITHIN_LIMITS" and "S$84" in tight["reason"]
    none = client.post("/api/v2/loop/basket/plan", json={"city": "singapore", "items": ["100W charger", "cable"]}).json()
    assert none["status"] == "NO_OFFER_FOR_ITEM" and none["missing"] == ["100W charger"]


def test_agent_plans_basket_for_several_items(client):
    body = client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "I need a 65W USB-C PD charger, a USB-C cable and a power bank under S$120"}]}).json()
    assert body["mode"] != "clarify" and body["basket"]["status"] == "OPTIMAL"
    # Each basket item reaches the shops as its own request.
    assert len(body["requests"]) == 3 and body["request"]["id"] == body["requests"][0]["id"]
    inbox = client.get("/api/v2/loop/cities/singapore/requests").json()
    assert {r["product"] for r in inbox} >= {"65W USB-C PD charger", "USB-C cable", "power bank"}
    assert any(t["tool"] == "plan_basket" for t in body["trace"])
    pt = client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "我需要一个65W充电器和一个充电宝"}]}).json()
    assert pt["basket"] and len(pt["basket"]["lines"]) == 2


def test_proof_plan_ranks_who_to_ask(client):
    body = client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()
    pp = body["proof_plan"]
    assert pp["engine"].startswith("EVSI") and pp["ranked"]
    top = pp["ranked"][0]
    assert top["shop"] == "Harbour Tech" and top["worth_asking"] and top["history"] == "assumed"
    lion = next(r for r in pp["ranked"] if r["shop"] == "Lion City Mobiles")
    assert lion["p_has_it"] < top["p_has_it"] and lion["net_value"] < top["net_value"]
    assert "Harbour Tech" in pp["advice"]


def test_engine_room_runs_every_engine(client):
    cat = client.get("/api/v2/loop/engines").json()
    assert len(cat["engines"]) == 9 and cat["retired"]
    for e in cat["engines"]:
        r = client.post(f"/api/v2/loop/engines/{e['id']}/run")
        assert r.status_code == 200, (e["id"], r.text)
        assert r.json()["result"], e["id"]
    research = client.post("/api/v2/loop/engines/research/run").json()["result"]
    assert research["cited_facts"]
    assert client.post("/api/v2/loop/engines/nope/run").status_code == 404
    a = client.get("/api/v2/loop/cities/singapore/analytics", params={"shop_id": "sg-harbour"}).json()
    assert a["command_center"]["queue"]


def test_invalid_model_json_falls_back_instead_of_500(client, monkeypatch):
    from app.commerce_loop import gemini as g
    from app.commerce_loop.intent import ShopperIntent, extract_intent

    class Resp:
        parsed = None
        text = '{"item": "power bank", "clarifying_question": "Which device do you intend to charge with'
        usage_metadata = None

    gem = g.Gemini()
    monkeypatch.setattr(type(gem), "is_mock", property(lambda self: False))
    monkeypatch.setattr(gem, "_client", lambda: object())
    monkeypatch.setattr(gem, "_generate", lambda client, **kw: Resp())
    intent, meta = extract_intent([{"role": "user", "text": "power bank 20000mAh under S$50"}], "singapore", gem)
    assert isinstance(intent, ShopperIntent) and meta["mode"] != "gemini"


def test_roles_are_enforced_when_enabled(client, monkeypatch):
    monkeypatch.setenv("LOOP_ENFORCE_ROLES", "true")
    shopper = {"X-NeedProof-Role": "shopper"}
    marina = {"X-NeedProof-Role": "shopkeeper", "X-NeedProof-Shop": "sg-marina"}
    harbour = {"X-NeedProof-Role": "shopkeeper", "X-NeedProof-Shop": "sg-harbour"}
    business = {"X-NeedProof-Role": "business"}
    admin = {"X-NeedProof-Role": "admin"}
    assert client.get("/api/v2/loop/whoami", headers=marina).json() == {"role": "shopkeeper", "shop_id": "sg-marina", "enforced": True}
    assert client.post("/api/v2/loop/shops/sg-marina/inventory/sample", headers=shopper).status_code == 403
    assert client.post("/api/v2/loop/shops/sg-marina/inventory/sample", headers=harbour).status_code == 403
    assert client.post("/api/v2/loop/shops/sg-marina/inventory/sample", headers=marina).status_code == 200
    assert client.get("/api/v2/loop/shops/sg-marina/dashboard", headers=business).status_code == 200
    assert client.get("/api/v2/loop/cities/singapore/insights", headers=marina).status_code == 403
    assert client.get("/api/v2/loop/cities/singapore/insights", headers=business).status_code == 200
    own = client.get("/api/v2/loop/cities/singapore/analytics", headers=marina).json()
    assert own["shop"]["id"] == "sg-marina"
    assert client.get("/api/v2/loop/cities/singapore/analytics", params={"shop_id": "sg-harbour"}, headers=marina).status_code == 403
    assert client.post("/api/v2/loop/demo/reset", headers=business).status_code == 403
    assert client.post("/api/v2/loop/demo/reset", headers=admin).status_code == 200
    # Shoppers can always ask; a request can be answered only by its shop (or a signed link).
    body = client.post("/api/v2/loop/agent/chat", headers=shopper, json={"city": "singapore", "history": [
        {"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()
    rid = body["request"]["id"]
    assert client.post(f"/api/v2/loop/requests/{rid}/reply", headers=shopper,
                       json={"shop_id": "sg-marina", "price": 49}).status_code == 403


def test_one_tap_reply_link_lets_a_shop_answer_without_an_account(client, monkeypatch):
    monkeypatch.setenv("LOOP_ENFORCE_ROLES", "true")
    from app.commerce_loop import store
    store.upsert_shops("singapore", [{"id": "osm-n42", "name": "Sim Lim Gadgets", "lat": 1.303, "lng": 103.853,
                                      "area": "Rochor", "source": "openstreetmap", "phone": "+65 6123 4567"}])
    shopper = {"X-NeedProof-Role": "shopper"}
    rid = client.post("/api/v2/loop/agent/chat", headers=shopper, json={"city": "singapore", "history": [
        {"role": "user", "text": "65W USB-C PD charger under S$60"}]}).json()["request"]["id"]
    link = client.get(f"/api/v2/loop/requests/{rid}/reply-link", params={"shop_id": "osm-n42"}, headers=shopper).json()
    assert link["direct"] and link["whatsapp_url"].startswith("https://wa.me/6561234567?text=")
    assert f"/r/{rid}?shop=osm-n42&t=" in link["url"] and "65W" in link["text"]
    token = link["url"].split("t=")[1]
    view = client.get(f"/api/v2/loop/requests/{rid}/for-shop", params={"shop_id": "osm-n42", "t": token}).json()
    assert view["shop"]["name"] == "Sim Lim Gadgets" and view["already_replied"] is None
    assert client.get(f"/api/v2/loop/requests/{rid}/for-shop", params={"shop_id": "osm-n42", "t": "forged"}).status_code == 403
    ok = client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "osm-n42", "price": 45, "reply_token": token, "mock_hint": {"wattage_w": 65}})
    assert ok.status_code == 200 and ok.json()["check"]["status"] == "PHOTO_MATCHES_REQUEST"
    bad = client.post(f"/api/v2/loop/requests/{rid}/reply", json={"shop_id": "sg-marina", "price": 1, "reply_token": token})
    assert bad.status_code == 403  # token is for one shop only


def test_snap_to_search_needs_live_model(client):
    import base64
    img = base64.b64encode(open(PHOTOS / "1_charger_65w_correct.jpg", "rb").read()).decode()
    r = client.post("/api/v2/loop/agent/snap", json={"image_base64": img, "image_mime": "image/jpeg"}).json()
    assert r["mode"] == "mock" and r["need"] is None


def test_any_product_with_reference_photo_and_photos_both_ways(client, monkeypatch):
    import base64
    monkeypatch.setenv("LOOP_ENFORCE_ROLES", "true")
    store.upsert_shops("singapore", [{"id": "gpl-cotton", "name": "Cotton Corner", "lat": 1.300, "lng": 103.855,
                                      "area": "Bugis", "source": "google_places", "phone": None, "kind": "clothing"}])
    ref = base64.b64encode(open(PHOTOS / "6_shirt_navy_floral_wanted.jpg", "rb").read()).decode()
    body = client.post("/api/v2/loop/agent/chat", headers={"X-NeedProof-Role": "shopper"}, json={
        "city": "singapore", "image_base64": ref, "image_mime": "image/jpeg",
        "history": [{"role": "user", "text": "Navy blue shirt with a small white floral print, size M, under S$40"}]}).json()
    assert body["intent"]["color"] == "navy blue" and body["intent"]["size"] == "M"
    assert body["ref_image_url"] and client.get(body["ref_image_url"]).status_code == 200
    rid = body["request"]["id"]
    assert body["request"]["category"] == "clothing"
    assert {n["shop"] for n in body["nearby"]} == {"Cotton Corner"}  # only clothing shops, not charger shops
    # Inbox: the clothing shop sees the shirt request with the shopper's photo; a charger shop does not.
    cotton = client.get("/api/v2/loop/cities/singapore/requests", params={"shop_id": "gpl-cotton"}).json()
    marina = client.get("/api/v2/loop/cities/singapore/requests", params={"shop_id": "sg-marina"}).json()
    assert [r["id"] for r in cotton] == [rid] and cotton[0]["ref_image_url"] == body["ref_image_url"]
    assert rid not in [r["id"] for r in marina]
    # The shop replies from WhatsApp with its photo; the shopper sees that photo.
    link = client.get(f"/api/v2/loop/requests/{rid}/reply-link", params={"shop_id": "gpl-cotton"},
                      headers={"X-NeedProof-Role": "shopper"}).json()
    token = link["url"].split("t=")[1]
    view = client.get(f"/api/v2/loop/requests/{rid}/for-shop", params={"shop_id": "gpl-cotton", "t": token}).json()
    assert view["request"]["ref_image_url"] == body["ref_image_url"]
    shop_photo = base64.b64encode(open(PHOTOS / "7_shirt_navy_floral_shop.jpg", "rb").read()).decode()
    client.post(f"/api/v2/loop/requests/{rid}/reply", json={
        "shop_id": "gpl-cotton", "price": 35, "reply_token": token, "image_base64": shop_photo, "image_mime": "image/jpeg"})
    resp = client.get(f"/api/v2/loop/requests/{rid}").json()["responses"][-1]
    assert resp["photo_url"] and client.get(resp["photo_url"]).status_code == 200


def test_design_mismatch_is_a_conflict():
    from app.commerce_loop.vision import PhotoClaim, check_photo
    req = {"product": "navy floral shirt", "category": "clothing", "specs": {"size": "M"}, "budget": 40}
    same = PhotoClaim(is_product_photo=True, product_category="shirt", is_requested_item_type=True, color="navy",
                      pattern_or_design="white floral", size_label="M", matches_reference=True)
    other = PhotoClaim(is_product_photo=True, product_category="shirt", is_requested_item_type=True, color="red",
                       pattern_or_design="check", size_label="M", matches_reference=False,
                       differences=["red check, not navy floral"])
    assert check_photo(req, same, 35)["status"] == "PHOTO_MATCHES_REQUEST"
    bad = check_photo(req, other, 29)
    assert bad["status"] == "PHOTO_CONFLICTS_WITH_REQUEST" and "red check" in bad["issues"][0]
    wrong_size = check_photo(req, same.model_copy(update={"size_label": "L"}), 35)
    assert wrong_size["status"] == "PHOTO_CONFLICTS_WITH_REQUEST"


def test_routing_summary_counts_requests_per_shop_and_category(client):
    store.upsert_shops("singapore", [{"id": "gpl-cotton2", "name": "Cotton Two", "lat": 1.30, "lng": 103.85,
                                      "area": "Bugis", "source": "google_places", "kind": "clothing",
                                      "maps_url": "https://maps.google.com/?cid=1", "rating": 4.5, "rating_count": 10}])
    client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "65W USB-C PD charger under S$60"}]})
    client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "Navy blue shirt with white floral print, size M"}]})
    r = client.get("/api/v2/loop/cities/singapore/routing").json()
    cats = {c["category"]: c for c in r["categories"]}
    assert cats["electronics"]["requests"] == 1 and cats["clothing"]["requests"] == 1
    assert r["shops"]["gpl-cotton2"]["by_category"] == {"clothing": 1}
    assert r["shops"]["sg-marina"]["by_category"] == {"electronics": 1}
    shops = {s["id"]: s for s in client.get("/api/v2/loop/cities/singapore/shops").json()}
    assert shops["gpl-cotton2"]["maps_url"] and shops["gpl-cotton2"]["rating"] == 4.5


def test_shop_dashboard_counts_only_requests_for_its_kind_of_shop(client):
    client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "65W USB-C PD charger under S$60"}]})
    client.post("/api/v2/loop/agent/chat", json={"city": "singapore", "history": [
        {"role": "user", "text": "2 kg rice and fresh fruit"}]})
    d = client.get("/api/v2/loop/shops/sg-marina/dashboard").json()
    products = [r["product"] for r in d["requests"]] + [m["product"] for m in d["missed_sales"]]
    assert products and not any("rice" in p or "fruit" in p for p in products)
    assert d["shop"]["kind"] == "electronics"
    assert {"category": "grocery", "requests": 1} in d["routing"]["routed_elsewhere"]
