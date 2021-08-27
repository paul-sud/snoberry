import os

import pytest


@pytest.fixture(scope="session")
def in_memory_db_setting():
    os.environ["DATABASE_URL"] = ":memory:"
