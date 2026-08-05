from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from backend.config import read_database_url


def main():
    engine = None

    try:
        engine = create_engine(read_database_url())
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, ValueError) as error:
        print(f"Database connection failed ({type(error).__name__}).")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    print(
        "Database connection succeeded "
        f"using {engine.url.get_backend_name()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
