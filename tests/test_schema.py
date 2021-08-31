import pytest
import strawberry

from snoberry.schema.mutation.mutation import Mutation
from snoberry.schema.query.query import Query


@pytest.fixture
def schema():
    schema = strawberry.Schema(query=Query, mutation=Mutation)
    return schema


@pytest.fixture
async def child(in_memory_db, schema):
    query = """
        mutation {
            createChild(
                input: {
                    name: "Joanne"
                }
            ) {
                id
                name
            }
        }
    """
    result = await schema.execute(query)
    assert not result.errors
    return result.data["createChild"]["id"]


@pytest.mark.asyncio
async def test_deep_mutation(in_memory_db, schema):
    """
    This mutation should first create a child, then create a parent linked to the child
    by the child's generated ID. Children should be stored in the DB as an array of IDs,
    without the ChildConnection indirection
    """
    query = """
        mutation {
            createParent(
                input: {
                    name: "Suzy"
                    children: [{
                        name: "Bupkiss"
                    }]
                }
            ) {
                name
                children {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
    """
    result = await schema.execute(query)
    assert not result.errors


@pytest.mark.asyncio
async def test_deep_mutation_with_existing_nested_type(in_memory_db, schema, child):
    query = """
        mutation {
            createParent(
                input: {
                    name: "Mary"
                    childIds: ["children:CHILD"]
                }
            ) {
                id
                name
                children {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
    """.replace(
        "CHILD", child
    )
    result = await schema.execute(query)
    assert not result.errors


@pytest.mark.asyncio
async def test_deep_mutation_nested_ids_and_types(in_memory_db, schema, child):
    query = """
        mutation {
            createParent(
                input: {
                    name: "Bootsy"
                    childIds: ["children:CHILD"],
                    children: [
                        {
                            name: "Kline"
                        }
                    ]
                }
            ) {
                id
                name
                children {
                    pageInfo {
                        startCursor
                        endCursor
                        hasNextPage
                    }
                    edges {
                        cursor
                        node {
                            name
                        }
                    }
                }
            }
        }
    """.replace(
        "CHILD", child
    )
    result = await schema.execute(query)
    assert not result.errors
    assert len(result.data["createParent"]["children"]["edges"]) == 2
