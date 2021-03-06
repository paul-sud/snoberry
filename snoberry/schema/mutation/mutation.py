import dataclasses
from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional, Tuple

import strawberry
from pydantic import BaseModel
from strawberry.type import StrawberryType

from ...database import database
from ...models import ChildModel, ParentModel
from ...schema.query.query import Child, Parent
from .input_types import ChildInput, ParentInput

_INPUT_NODES = {ParentInput, ChildInput}


async def validate_id(id: str, field_name: str) -> None:
    tablename, item_id = id.split(":")
    type_from_id = get_type_from_id_field_name(field_name)
    if tablename != type_from_id:
        raise ValueError(
            "ID type {type_from_id} does not match expected type {tablename}"
        )
    table = database.get_table_by_name(tablename)
    query = table.select().where(table.c.id == item_id)
    result = await database.database.fetch_one(query=query)
    if result is None:
        raise ValueError(f"ID not in database: {id}")


def get_type_from_id_field_name(id_field_name: str) -> str:
    """
    Given a field name like "child_ids" or "parent_id" return the plural form of the
    first part, i.e. "children" or "parents" for these examples.
    """
    no_suffix = id_field_name.removesuffix("_ids").removesuffix("_id")
    if no_suffix == "child":
        return "children"
    return f"{no_suffix}s"


async def validate_id_fields(item: BaseModel) -> None:
    """
    Validate that any linked IDs on the object are in the database. This is based on the
    field name. `typex_id` fields will be checked as a valid link to a `typex`.
    `typex_ids` fields, which are lists of links, will be checked one by one.

    Because the code that interacts with the DB is async, it cannot be used as a
    Pydantic validator. Some would argue that it's better to avoid involving Pydantic
    in such concerns anyway.
    https://github.com/samuelcolvin/pydantic/issues/857

    It's possible to wrap an async function synchronously using
    `asyncio.run_coroutine_threadsafe` or with libraries like `aio-libs` `janus`, but
    these require creating an event loop in a separate thread or thread pool, which
    seems like overkill just to do this validation.
    https://www.reddit.com/r/Python/comments/6m826s/calling_async_functions_from_synchronous_functions/
    """
    for field_name, value in item:
        if field_name.endswith("_id"):
            await validate_id(value, field_name)
        elif field_name.endswith("_ids"):
            for each_value in value:
                await validate_id(each_value, field_name)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_child(self, input: ChildInput) -> Child:
        validated = to_pydantic(input)
        table = database.get_table_by_name("children")
        result = await database.database.execute(
            query=table.insert(), values={"data": validated.dict()}
        )
        query = table.select().where(table.c.id == result)
        row = await database.database.fetch_one(query=query)
        child_model = ChildModel.construct(**row.data)
        return Child(id=row.id, **child_model.dict())

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
        parent = ParentModel.construct(**row.data)
        return Parent(id=row.id, **parent.dict())


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


def _get_database_table_from_input_node(node: StrawberryType) -> str:
    singular_name = type(node).__name__.removesuffix("Input").lower()
    if singular_name == "child":
        return "children"
    return singular_name + "s"
