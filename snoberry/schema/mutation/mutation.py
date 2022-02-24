from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING

import strawberry
from apischema import serialize, deserialize

from ...database import database
from ...schema.query.query import Child, HasTableName, Parent


if TYPE_CHECKING:
    from strawberry.type import StrawberryType


@strawberry.input
class ChildInput:
    name: str


@strawberry.input
class ParentInput:
    name: str
    children: Optional[List[ChildInput]] = None


_INPUT_NODES = {ParentInput, ChildInput}


async def validate_id(id: str, field_name: str, expected_link_to_type: HasTableName) -> None:
    tablename, item_id = id.split(":")
    if tablename != expected_link_to_type.table_name:
        raise ValueError(
            "ID type {type_from_id} does not match expected type {tablename}"
        )
    table = database.get_table_by_name(tablename)
    query = table.select().where(table.c.id == item_id)
    result = await database.database.fetch_one(query=query)
    if result is None:
        raise ValueError(f"ID not in database: {id}")


async def validate_id_fields(item: "StrawberryType") -> None:
    """
    Validate that any linked IDs on the object are in the database. This is based on the
    field name. `typex_id` fields will be checked as a valid link to a `typex`.
    `typex_ids` fields, which are lists of links, will be checked one by one. Async
    validators are not possible in apischema, can't use the usual @validator decorator.

    It's possible to wrap an async function synchronously using
    `asyncio.run_coroutine_threadsafe` or with libraries like `aio-libs` `janus`, but
    these require creating an event loop in a separate thread or thread pool, which
    seems like overkill just to do this validation.
    https://www.reddit.com/r/Python/comments/6m826s/calling_async_functions_from_synchronous_functions/
    """
    for field_name, value in vars(item).items():
        if field_name.endswith("_id"):
            await validate_id(value, field_name, expected_link_to_type)
        elif field_name.endswith("_ids"):
            for each_value in value:
                await validate_id(each_value, field_name, expected_link_to_type)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_child(self, input: ChildInput) -> Child:
        serialized = serialize(input)
        # Runs apischema validation
        deserialize(Child, serialized)
        table = database.get_table_by_name("children")
        result = await database.database.execute(
            query=table.insert(), values={"data": serialized}
        )
        query = table.select().where(table.c.id == result)
        row = await database.database.fetch_one(query=query)
        return Child(id=row.id, **row.data)

    @strawberry.mutation
    async def create_parent(self, input: ParentInput) -> Parent:
        """
        Cannot validate the whole input graph in Pydantic because we first must create
        the children, so that we can then pass the required ids to the Pydantic model
        validation. This is where a transaction is desired, otherwise we might create
        some objects in the database corresponding to a valid subgraph, then encounter
        a Pydantic validation error, and need to clean up the subgraph ourselves.

        TODO: wrap entire mutation in transaction
        https://www.encode.io/databases/connections_and_transactions/
        async with database.transaction():
        """
        # Makes sense since a parent must have children
        # However need to be smarter if it's optional, to generalize
        # You can't have unions in input types in GraphQL yet unfortunately
        if input.children is None and input.child_ids is None:
            raise ValueError("must specify either or both of child_ids and children")
        nodes, node_ids_to_children = depth_first_search(input)
        node_ids_to_guids: Dict[int, str] = {}
        for node in nodes:
            database_table_name = _get_database_table_from_input_node(node)
            extras: defaultdict[str, List[str]] = defaultdict(list)
            for field_name, child_node_ids in node_ids_to_children[id(node)].items():
                id_field_name = _get_id_field_from_input_field_name(field_name)
                extras[id_field_name].extend(
                    node_ids_to_guids[node_id] for node_id in child_node_ids
                )
                if getattr(node, id_field_name, None) is not None:
                    extras[id_field_name].extend(getattr(node, id_field_name))
            validated = to_pydantic(node, extras)
            await validate_id_fields(validated)
            table = database.get_table_by_name(database_table_name)
            query = table.insert()  # .returning(table.c.id)
            # In this case of sqlalchemy `result` is the lastrowid which is the same as
            # the autoincrementing primary key. I don't think it's the same for other
            # dialects. Could probably update the query above
            result = await database.database.execute(
                query=query, values={"data": validated.dict()}
            )
            guid = f"{database_table_name}:{result}"
            node_ids_to_guids[id(node)] = guid
        query = table.select().where(table.c.id == result)
        row = await database.database.fetch_one(query=query)
        return Parent(id=row.id, **row.data)


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
    # TODO: Maybe should use weakrefs here so storing pointers to nodes doesn't prevent
    # garbage collection?
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
        if type(field) in _INPUT_NODES:
            yield field_name, field
        if isinstance(field, list):
            for item in flatten(field):
                if type(item) in _INPUT_NODES:
                    yield field_name, item


def flatten(value: List[Any]) -> Iterator[Any]:
    for item in value:
        if isinstance(item, list):
            yield from flatten(item)
        yield item


def _get_id_field_from_input_field_name(input_field_name: str) -> str:
    """
    Map plural input fields like children to the appropriate field child_ids in this
    case.
    """
    if input_field_name == "children":
        return "child_ids"
    return input_field_name.rstrip("s") + "_ids"


def _get_database_table_from_input_node(node: "StrawberryType") -> str:
    singular_name = type(node).__name__.removesuffix("Input").lower()
    if singular_name == "child":
        return "children"
    return singular_name + "s"
