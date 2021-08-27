import pytest

from snoberry.schema import schema


@pytest.fixture(scope="module")
def child():
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
    schema.execute_sync(query)


def test_deep_mutation():
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
    result = schema.execute_sync(query)
    assert not result.errors


def test_deep_mutation_with_existing_nested_type(child):
    query = """
        mutation {
            createParent(
                input: {
                    name: "Mary"
                    childIds: ["children:2"]
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
    """
    result = schema.execute_sync(query)
    print(result.data)
    assert not result.errors


def test_deep_mutation_nested_ids_and_types(child):
    query = """
        mutation {
            createParent(
                input: {
                    name: "Bootsy"
                    childIds: ["children:2"],
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
    """
    result = schema.execute_sync(query)
    assert not result.errors
