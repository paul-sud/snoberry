import strawberry

from .mutation.mutation import Mutation
from .query.query import Query

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[strawberry.extensions.tracing.apollo.ApolloTracingExtension],
)
