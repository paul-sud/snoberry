import asyncio
import os

import pytest

from snoberry.app import on_shutdown, on_startup


@pytest.fixture(scope="session")
def in_memory_db_setting(tmp_path_factory):
    """
    Using in memory sqlite ":memory:" causes issues:
    https://stackoverflow.com/questions/21766960/operationalerror-no-such-table-in-flask-with-sqlalchemy

    Better to just use a temp db file. In production this would probably be Postgres
    anyway so the side effects are fine.
    """
    os.environ[
        "DATABASE_URL"
    ] = f"sqlite:///{str(tmp_path_factory.mktemp('database') / 'test.db')}"


@pytest.fixture(scope="session", autouse=True)
async def in_memory_db(in_memory_db_setting):
    await on_startup()
    yield
    # Will be executed after the last test
    await on_shutdown()


@pytest.fixture(scope="session")
def event_loop():
    """
    Will get errors using session-scoped fixtures with async
    https://github.com/pytest-dev/pytest-asyncio/issues/75
    https://stackoverflow.com/questions/63713575/pytest-issues-with-a-session-scoped-fixture-and-asyncio
    """
    return asyncio.get_event_loop()
