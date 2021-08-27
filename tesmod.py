import dataclasses
import random
from base64 import b64decode, b64encode
from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional, Tuple

import strawberry
from pydantic import BaseModel, conlist, validator
from strawberry.schema import default_validation_rules
from strawberry.tools import depth_limit_validator
from strawberry.type import StrawberryType


def get_cursor_from_offset(offset: int) -> str:
    """
    The arrayconnection:OFFSET cursor is how `graphql-relay-js` does it.
    """
    return b64encode(f"arrayconnection:{offset}".encode()).decode()


def get_offset_from_cursor(cursor: str) -> int:
    """
    Inverse of cursor_from_offset
    """
    return int(b64decode(cursor.encode()).decode().split(":")[-1])


def get_start_and_end_cursor(
    array_length: int, first: Optional[int], after: Optional[str]
) -> Tuple[str, str]:
    """
    Given the array's length and pagination arguments, return the start and end cursors
    needed to populate pageInfo
    """
    start_offset = 0
    if after is not None:
        start_offset = get_offset_from_cursor(after) + 1
    start_cursor = get_cursor_from_offset(start_offset)
    end_offset = array_length - 1
    if first is not None:
        end_offset = start_offset + first - 1
    end_cursor = get_cursor_from_offset(end_offset)
    return start_cursor, end_cursor


def get_edges_to_return(
    all_edges: List[Any], after: Optional[str] = None, first: Optional[int] = None
) -> List[Any]:
    """
    Adapted from Relay cursor spec: https://relay.dev/graphql/connections.htm#
    `before/last` not supported for simplicity.

    EdgesToReturn(allEdges, before, after, first, last)
        Let edges be the result of calling ApplyCursorsToEdges(allEdges, before, after).
        If first is set:
            If first is less than 0:
                Throw an error.
            If edges has length greater than than first:
                Slice edges to be of length first by removing edges from the end of edges.
        If last is set:
            If last is less than 0:
                Throw an error.
            If edges has length greater than than last:
                Slice edges to be of length last by removing edges from the start of edges.
        Return edges.
    """
    edges = apply_cursors_to_edges(all_edges=all_edges, after=after)
    end_index = len(edges)
    if first is not None:
        if first < 0:
            raise ValueError("First should be greater than 0")
        end_index = first
    return edges[:end_index]


def apply_cursors_to_edges(
    all_edges: List[Any], after: Optional[str] = None
) -> List[Any]:
    """
    Adapted from Relay cursor spec: https://relay.dev/graphql/connections.htm#
    `before` not supported for simplicity.

    ApplyCursorsToEdges(allEdges, before, after)
        Initialize edges to be allEdges.
        If after is set:
            Let afterEdge be the edge in edges whose cursor is equal to the after argument.
            If afterEdge exists:
                Remove all elements of edges before and including afterEdge.
        If before is set:
            Let beforeEdge be the edge in edges whose cursor is equal to the before argument.
            If beforeEdge exists:
                Remove all elements of edges after and including beforeEdge.
        Return edges.
    """
    start_index = 0
    if after is not None:
        offset = get_offset_from_cursor(after)
        start_index = offset + 1
    return all_edges[start_index:]


def has_previous_page(
    all_edges: List[Any], after: Optional[str] = None, first: Optional[int] = None
) -> bool:
    """
    HasPreviousPage(allEdges, before, after, first, last)
        If last is set:
            Let edges be the result of calling ApplyCursorsToEdges(allEdges, before, after).
            If edges contains more than last elements return true, otherwise false.
        If after is set:
            If the server can efficiently determine that elements exist prior to after, return true.
        Return false.
    """
    if after is not None:
        offset = get_offset_from_cursor(after)
        return offset != 0
    return False


def has_next_page(
    all_edges: List[Any], after: Optional[str] = None, first: Optional[int] = None
) -> bool:
    """
    HasNextPage(allEdges, before, after, first, last)
        If first is set:
            Let edges be the result of calling ApplyCursorsToEdges(allEdges, before, after).
            If edges contains more than first elements return true, otherwise false.
        If before is set:
            If the server can efficiently determine that elements exist following before, return true.
        Return false.
    """
    if first is not None:
        offset = 0
        if after is not None:
            offset = get_offset_from_cursor(after)
        return len(all_edges) > offset + 1 + first
    return False


@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None


@strawberry.interface
class Node:
    """
    Defining and enforcing the interface in Pydantic makes IDs required when validating,
    as is the case when setting `is_interface=True`
    """

    id: str


class ChildModel(BaseModel):
    name: str


@strawberry.experimental.pydantic.type(model=ChildModel, fields=["name"])
class Child(Node):
    pass


@strawberry.type
class ChildEdge:
    cursor: str
    child_id: strawberry.Private[str]

    @strawberry.field
    def node(self) -> Child:
        """
        Identical code to other resolvers
        """
        data = ChildModel.construct(**database[f"{self.child_id}"])
        return Child.from_pydantic(data, extra={"id": self.child_id})


@strawberry.type
class ChildConnection:
    page_info: PageInfo
    child_ids: strawberry.Private[List[str]]

    @strawberry.field
    def edges(self) -> List[ChildEdge]:
        """
        The cursors should be encoded in base64
        """
        return get_edges_to_return(
            [
                ChildEdge(child_id=child_id, cursor=get_cursor_from_offset(i))
                for i, child_id in enumerate(self.child_ids)
            ]
        )


def validate_id(id: str) -> str:
    if id not in database:
        raise ValueError(f"ID not in database: {id}")
    return id


class ParentModel(BaseModel):
    """
    Would be nice to attach validators to the model functionally, but it's not possible.
    See https://github.com/samuelcolvin/pydantic/issues/2076

    Instead we just use the resuse validators to verify IDs
    https://pydantic-docs.helpmanual.io/usage/validators/#reuse-validators

    May be worth implementing as a root validator checking all `_id/_ids` fields.
    """

    name: str
    child_ids: conlist(str, min_items=1)

    # Validators
    _validate_child_ids = validator("child_ids", allow_reuse=True, each_item=True)(
        validate_id
    )


@strawberry.experimental.pydantic.type(model=ParentModel, fields=["name"])
class Parent(Node):
    """
    Need to specify children here since resolver must take arguments per Relay spec.
    """

    child_ids: strawberry.Private[List[str]]

    @strawberry.field
    def children(
        self, first: Optional[int] = None, after: Optional[str] = None
    ) -> ChildConnection:
        start_cursor, end_cursor = get_start_and_end_cursor(
            len(self.child_ids), first=first, after=after
        )
        return ChildConnection(
            child_ids=self.child_ids,
            page_info=PageInfo(
                start_cursor=start_cursor,
                end_cursor=end_cursor,
                has_next_page=has_next_page(self.child_ids, first=first, after=after),
                has_previous_page=has_previous_page(
                    self.child_ids, first=first, after=after
                ),
            ),
        )


@strawberry.experimental.pydantic.input(model=ChildModel, fields=["name"])
class ChildInput:
    pass


@strawberry.experimental.pydantic.input(model=ParentModel, fields=["name"])
class ParentInput:
    children: Optional[List[ChildInput]] = None
    child_ids: Optional[List[str]] = None


database = {}
nodes = {"parent": Parent, "child": Child}
input_nodes = {ParentInput, ChildInput}


def get_id_field_from_input_field_name(input_field_name: str) -> str:
    """
    Map plural input fields like children to the appropriate field child_ids in this
    case.
    """
    if input_field_name == "children":
        return "child_ids"
    return input_field_name.rstrip("s") + "_ids"


def get_database_table_from_node(node: StrawberryType) -> str:
    singular_name = type(node).__name__.removesuffix("Input").lower()
    if singular_name == "child":
        return "children"
    return singular_name + "s"


def to_pydantic(
    strawberry_model: StrawberryType, extras: Optional[Dict[str, Any]] = None
) -> BaseModel:
    """
    Adapted from strawberry.experimental.pydantic.object_type.py. Want to pass extras
    not in the input model to the Pydantic model. You can set attributes on the
    strawberry types, however when `dataclass.asdict` the extra properties are not
    returned and not passed to the Pydantic model constructor.

    TODO: Strawberry PR to add inbuilt support for passing extras to Pydantic
    """
    pydantic_model = globals()[
        type(strawberry_model).__name__.removesuffix("Input") + "Model"
    ]
    instance_kwargs = dataclasses.asdict(strawberry_model)
    if extras is not None:
        instance_kwargs.update(extras)
    return pydantic_model(**instance_kwargs)


@strawberry.type
class Query:
    @strawberry.field
    def node(self, id: str) -> Node:
        """
        `node` root field required for Relay (refetching etc)
        """
        typename = id.split(":")[0]
        data = database[id]
        # No need for pydantic validation, data in DB is well-formed
        return nodes[typename](id=id, **data)

    @strawberry.field
    def get_parent(self, id: str) -> Parent:
        """
        Using `construct` skips validation and should be much faster. It's ok because
        we trust that the data in the database was validated at creation/update
        """
        data = ParentModel.construct(**database[f"parents:{id}"])
        return Parent.from_pydantic(data)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_child(self, input: ChildInput) -> Child:
        validated = to_pydantic(input)
        database["children:2"] = validated.dict()
        child_model = ChildModel.construct(**database["children:2"])
        return Child.from_pydantic(child_model, extra={"id": "children:2"})

    @strawberry.mutation
    def create_parent(self, input: ParentInput) -> Parent:
        """
        Cannot validate the whole input graph in Pydantic because we first must create
        the children, so that we can then pass the required ids to the Pydantic model
        validation. This is where a transaction is desired, otherwise we might create
        some objects in the database corresponding to a valid subgraph, then encounter
        a Pydantic validation error, and need to clean up the subgraph ourselves.

        TODO: wrap entire mutation in transaction
        https://www.encode.io/databases/connections_and_transactions/
        async with database.transaction():

        The design of this API is based on deep mutations in Dgraph. Essentially, you
        should be able to pass in a mix of child objects containing info needed to
        create them, or a child object with an existing ID. You can see
        examples here:
        https://dgraph.io/docs/graphql/mutations/deep/
        https://github.com/dgraph-io/dgraph/blob/master/graphql/resolve/add_mutation_test.yaml

        Interestingly, in one of the examples that adds a new author with two existing
        posts, the existing posts are detached from their current author, if I
        understand correctly. I think posts are only allowed to have one author? It
        seems it should raise an error, especially given our use case. You can imagine
        adding a new experiment with existing replicates, where the replicates already
        have an experiment. In DGraph, this would delete the replicate from the old
        experiment's replicates array, which seems bad.
        https://github.com/dgraph-io/dgraph/blob/master/graphql/resolve/add_mutation_test.yaml#L2029
        """
        # result = input.to_pydantic()  # Doesn't work since need to make child_id list
        # Makes sense since a parent must have children
        # However need to be smarter if it's optional, to generalize
        if input.children is None and input.child_ids is None:
            raise ValueError("must specify either or both of child_ids and children")
        nodes, node_ids_to_children = depth_first_search(input)
        node_ids_to_guids = {}
        for node in nodes:
            database_table = get_database_table_from_node(node)
            # In practice the id would be an autoincrement primary key that we would get
            # from the database when row is added
            database_id = random.randint(1, 100)
            extras: defaultdict[str, List[str]] = defaultdict(list)
            for field_name, child_node_ids in node_ids_to_children[id(node)].items():
                id_field_name = get_id_field_from_input_field_name(field_name)
                extras[id_field_name].extend(
                    node_ids_to_guids[node_id] for node_id in child_node_ids
                )
                if getattr(node, id_field_name, None) is not None:
                    extras[id_field_name].extend(getattr(node, id_field_name))
            # validated = node.to_pydantic()  # Doesn't always work since need ids
            validated = to_pydantic(node, extras)
            guid = f"{database_table}:{database_id}"
            database[guid] = validated.dict()
            print(f"Created {guid}")
            node_ids_to_guids[id(node)] = guid
        parent = ParentModel.parse_obj(database[guid])
        return Parent(id=guid, **parent.dict())


def depth_first_search(
    node: Any, node_count_limit: int = 100
) -> Tuple[List[Any], Dict[int, defaultdict[str, List[int]]]]:
    """
    Perform DFS on a graph of input objects. Return nodes in reverse order of traversal
    so the root is last. You could use BFS too, the main point is that child nodes come
    before parent nodes in the returned iterator, so we have an order to create them
    such that child nodes are created before their parents.
    """
    stack = []
    explored = {}
    node_ids_to_children = {}
    # Maybe should use weakrefs here so storing pointers to nodes doesn't prevent them
    # from being garbage collected?
    explored[id(node)] = node
    stack.append(node)
    while stack:
        current_node = stack.pop()
        child_node_ids_by_field = defaultdict(list)
        for field_name, child_node in get_child_nodes(current_node):
            child_node_id = id(child_node)
            child_node_ids_by_field[field_name].append(child_node_id)
            if child_node_id not in explored:
                explored[id(child_node)] = child_node
                if len(explored) > node_count_limit:
                    raise ValueError("Graph has too many nodes")
                stack.append(child_node)
        node_ids_to_children[id(current_node)] = child_node_ids_by_field
    return list(reversed(explored.values())), node_ids_to_children


def get_child_nodes(node: Any) -> Iterator[Tuple[str, Any]]:
    """
    Must recurse through lists, which per GraphQL spec can be arbitrarily nested.
    """
    for field_name, field in vars(node).items():
        # # If traversing the pydantic graph
        # if isinstance(field, BaseModel):
        if type(field) in input_nodes:
            yield field_name, field
        if isinstance(field, list):
            for item in flatten(field):
                if type(item) in input_nodes:
                    yield field_name, item


def flatten(value: List[Any]) -> Iterator[Any]:
    for item in value:
        if isinstance(item, list):
            yield from flatten(item)
        yield item


validation_rules = default_validation_rules + [depth_limit_validator(10)]
schema = strawberry.Schema(query=Query, mutation=Mutation)

# This mutation should first create a child, then create a parent linked to the child
# by the child's generated ID. Children should be stored in the DB as an array of IDs,
# without the ChildConnection indirection
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
result = schema.execute_sync(query, validation_rules=validation_rules)
print(result)


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


# Similar to above except should just link to existing child instead of creating
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


# Mixes both link to existing child and creating new child
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
print(result.data)
