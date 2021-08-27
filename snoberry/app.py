import sqlalchemy
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from strawberry.asgi import GraphQL

from .database import database, metadata
from .schema import schema
from .settings import DATABASE_URL, DEBUG, GRAPHQL_ROUTE


async def on_startup():
    # TODO: should use alembic or something
    engine = sqlalchemy.create_engine(str(DATABASE_URL), echo=True)
    metadata.create_all(engine)
    await database.connect()


async def on_shutdown():
    await database.disconnect()


app = Starlette(debug=DEBUG, on_startup=[on_startup], on_shutdown=[on_shutdown])
app.add_middleware(
    CORSMiddleware, allow_headers=["*"], allow_origins=["*"], allow_methods=["*"]
)
graphql_app = GraphQL(schema, debug=DEBUG)
app.add_route(GRAPHQL_ROUTE, graphql_app)
app.add_websocket_route(GRAPHQL_ROUTE, graphql_app)
