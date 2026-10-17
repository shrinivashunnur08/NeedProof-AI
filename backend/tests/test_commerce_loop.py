"""Commerce loop tests. Gemini runs in mock mode, so no network or spend."""
import pytest
from fastapi.testclient import TestClient

from app.commerce_loop import store
from app.commerce_loop.locale import Money, engine_scale, parse_money, resolve_city
from app.commerce_loop.providers import get_providers
from app.commerce_loop.vision import PhotoClaim, check_photo


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOP_DB_PATH", str(tmp_path / "loop.db"))
    monkeypatch.setenv("GEMINI_BACKEND", "mock")
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
    assert tools[0] == "find_offers" and "ask_nearby_shops" in tools
    shops = {o["shop"]: o for o in body["offers"]}
    assert shops["Harbour Tech (demo)"]["usable"] is True
    assert shops["Lion City Mobiles (demo)"]["usable"] is False  # listed but out of stock
    marina = shops["Marina Gadgets (demo)"]
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
    assert brief["brief"]["headline"] and len(brief["brief"]["actions"]) == 3


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
