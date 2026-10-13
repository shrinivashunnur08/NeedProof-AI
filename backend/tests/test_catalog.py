
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db.models import Base
from app.db.seed import seed_data
from app.db.session import get_db
from app.main import app


def test_catalog_end_to_end():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with factory() as session:
        assert seed_data(session) == 6
        assert seed_data(session) == 0

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        environment="development",
        demo_write_key="test-only-secret",
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/catalog/products?category=charger"
            )

            assert response.status_code == 200

            products = response.json()

            assert len(products) == 3
            assert products[0]["price_minor"] == 72000
            assert products[0]["stock_freshness"] == "STALE"
            assert products[0]["is_demo"] is True

            response = client.get(
                "/api/catalog/evidence",
                params={"product_id": products[0]["id"]},
            )

            assert response.status_code == 200

            overview = client.get(
                "/api/catalog/overview"
            ).json()

            assert overview["merchant_count"] == 3

            inventory_id = products[0]["inventory_id"]

            # Unauthorized changes must fail.
            response = client.patch(
                f"/api/catalog/inventory/{inventory_id}",
                json={"stock_on_hand": 0},
            )

            assert response.status_code == 403

            # Authorized development-only update.
            response = client.patch(
                f"/api/catalog/inventory/{inventory_id}",
                json={"stock_on_hand": 0},
                headers={
                    "X-Demo-Key": "test-only-secret"
                },
            )

            assert response.status_code == 200
            assert (
                response.json()["stock_freshness"]
                == "UNCHECKED"
            )

            updated = client.get(
                "/api/catalog/products?category=charger"
            ).json()

            assert updated[0]["stock_available"] == 0

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
