import strawberry
import asyncio
from pprint import pprint

from dataclasses import dataclass, field

from apischema import deserialize, schema


def resolver() -> int:
    return 2


@strawberry.interface
class Node:
    guid: int


@strawberry.type
class Nested:
    id: int


@strawberry.type
class Resource(Node):
    id: int
    nested: Nested
    tags: list[int] = field(
        default_factory=list,
        metadata=schema(
            description="regroup multiple resources", max_items=3, unique=True
        ),
    )

    @strawberry.field(description="Name")
    def count(self) -> int:
        return 3

    count2: int = strawberry.field(resolver=resolver)


@strawberry.type
class Query:
    @strawberry.field
    def resource(self) -> Resource:
        return Resource(id=1, tags=[1, 2, 3], nested=Nested(1), guid=3)


schema = strawberry.Schema(query=Query)


async def test():
    query = """
        query {
            resource {
                id
                tags
                count
                count2
                nested {
                    id
                }
            }
        }
    """
    result = await schema.execute(query)
    print(result.data)

asyncio.run(test())

deserialize(
    Resource, {"id": 42, "tags": [1, 2, 3], "nested": {"id": 1}, "guid": 4}
)
