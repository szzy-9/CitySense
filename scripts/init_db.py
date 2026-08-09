import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.app import create_app
from backend.database import database_health, initialize_database


def main():
    app = create_app()
    with app.app_context():
        initialized = initialize_database()
        if not initialized or database_health() != "connected":
            print("Database initialization could not be verified.")
            return 1

    print("Backend-owned route_searches schema is ready; DS tables were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
