import strawberry
from strawberry.extensions.tracing.apollo import ApolloTracingExtension

from .mutation.mutation import Mutation
from .query.query import Query

schema = strawberry.Schema(
    query=Query, mutation=Mutation, extensions=[ApolloTracingExtension]
)
