import strawberry
from strawberry.extensions import ParserCache, QueryDepthLimiter, ValidationCache
from strawberry.extensions.tracing.apollo import ApolloTracingExtension

from ..settings import (
    APOLLO_TRACING_ENABLED,
    PARSER_CACHE_MAX_SIZE,
    QUERY_MAX_DEPTH_LIMIT,
    VALIDATION_CACHE_MAX_SIZE,
)
from .mutation.mutation import Mutation
from .query.query import Query

extensions = [
    ParserCache(maxsize=PARSER_CACHE_MAX_SIZE),
    QueryDepthLimiter(max_depth=QUERY_MAX_DEPTH_LIMIT),
    ValidationCache(maxsize=VALIDATION_CACHE_MAX_SIZE),
]

if APOLLO_TRACING_ENABLED:
    extensions.append(ApolloTracingExtension)

# TODO: add `types` argument below to expose concrete types satistying Node interface
# since they are not used as a type for any field
schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=extensions)
