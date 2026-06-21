import os
import tempfile

# Must be set before any application imports — SqliteDatabase reads DATABASE_PATH at import time.
_db_path = os.path.join(tempfile.gettempdir(), "agrosafe_test_edge.db")
os.environ.setdefault("DATABASE_PATH", _db_path)

import pytest


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    from shared.infrastructure.database import init_db
    init_db()
    yield
    try:
        os.remove(_db_path)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="session")
def app(_init_database):
    from main import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
