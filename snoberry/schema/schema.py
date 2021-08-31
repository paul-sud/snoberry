import strawberry
from strawberry.extensions.tracing.apollo import ApolloTracingExtension

from ..settings import APOLLO_TRACING_ENABLED
from .mutation.mutation import Mutation
from .query.query import Query

extensions = []

if APOLLO_TRACING_ENABLED:
    extensions.append(ApolloTracingExtension)

schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=extensions)
