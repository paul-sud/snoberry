import sqlalchemy
from databases import Database

from .settings import DATABASE_URL

metadata = sqlalchemy.MetaData()

experiments = sqlalchemy.Table(
    "experiments",
    metadata,
    sqlalchemy.Column("uuid", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("data", sqlalchemy.JSON),
)

files = sqlalchemy.Table(
    "files",
    metadata,
    sqlalchemy.Column("uuid", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("data", sqlalchemy.JSON),
)


parents = sqlalchemy.Table(
    "parents",
    metadata,
    sqlalchemy.Column("uuid", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("data", sqlalchemy.JSON),
)

database = Database(DATABASE_URL)
