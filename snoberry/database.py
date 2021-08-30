from functools import cached_property
from typing import Dict, Iterable

import databases
import sqlalchemy

from .settings import DATABASE_URL


class Database:
    def __init__(self) -> None:
        self._tables: Dict[str, sqlalchemy.Table] = {}

    def populate_tables(self, table_names: Iterable[str]) -> None:
        for table_name in table_names:
            if table_name not in self._tables:
                self._tables[table_name] = sqlalchemy.Table(
                    table_name,
                    self.metadata,
                    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
                    sqlalchemy.Column("data", sqlalchemy.JSON),
                )

    @cached_property
    def database(self) -> databases.Database:
        return databases.Database(DATABASE_URL)

    @cached_property
    def metadata(self) -> sqlalchemy.MetaData:
        return sqlalchemy.MetaData()

    def get_table_by_name(self, name: str) -> sqlalchemy.Table:
        return self._tables[name]


database = Database()
