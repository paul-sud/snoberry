from databases import DatabaseURL
from starlette.config import Config

config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
APOLLO_TRACING_ENABLED = config("APOLLO_TRACING_ENABLED", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", cast=DatabaseURL)
GRAPHQL_ROUTE = config("GRAPHQL_ROUTE", default="/graphql")
PARSER_CACHE_MAX_SIZE = config("PARSER_CACHE_MAX_SIZE", cast=int, default=100)
VALIDATION_CACHE_MAX_SIZE = config("PARSER_CACHE_MAX_SIZE", cast=int, default=100)
QUERY_MAX_DEPTH_LIMIT = config("QUERY_MAX_DEPTH_LIMIT", cast=int, default=20)
