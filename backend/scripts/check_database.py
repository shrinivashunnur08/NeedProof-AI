
from sqlalchemy import text

from app.db.session import get_engine


def main():
    engine = get_engine()

    print("NeedProof AI — Database Connectivity")
    print("------------------------------------")
    print("Database dialect:", engine.dialect.name)

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        ).scalar_one()

    print("Connectivity test:", "PASS" if result == 1 else "FAIL")


if __name__ == "__main__":
    main()
