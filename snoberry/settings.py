from databases import DatabaseURL
from starlette.config import Config

config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
APOLLO_TRACING_ENABLED = config("APOLLO_TRACING_ENABLED", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", cast=DatabaseURL)
GRAPHQL_ROUTE = "/graphql"
