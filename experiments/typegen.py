"""
`strawberry.tools.create_type` doesn't work for fields that don't have resolvers.
So we first dynamically create the class with `type`, making sure to populate
`__annotations__`, then wrap the class in `strawberry.type`, and finally expose the
generated types in this module by patching `globals()`

While an interesting use of Python's dynamic capabilities, it doesn't work well with
static type checkers. For instance, `mypy`, in the words of Guido van Rossum,
"doesn't run your code, it only reads it, and it only looks at the types of attributes,
not at actions like setattr()."
- https://github.com/python/mypy/issues/5719#issuecomment-426427083

Given this, code generation is probably preferable.

Outputs should be the same as ChildConnection and ChildEdge classes defined in query.
"""

from typing import Any, Callable, List, Type

import strawberry

from snoberry.models import MODELS
from snoberry.relay.schema import Node, PageInfo
from snoberry.relay.utils import get_cursor_from_offset, get_edges_to_return
from snoberry.schema.mutation.mutation import get_type_from_id_field_name
from snoberry.schema.query.query import _NODES


def make_node_resolver(node_type: Type[Any], id_field: str) -> Callable[[Node], Node]:
    """
    Higher order function to create a resolver resolving to a specific node, to be used
    as resolver to `X` in `XEdge` types.
    """

    def resolve_node(root: Node) -> Node:
        typename, _ = getattr(root, id_field).split(":")
        # In prod get the data from the database here.
        modeled = MODELS[typename](name="Bill")
        return node_type(id="3", **modeled.dict())

    return resolve_node


def make_edge_resolver(
    edge_type: Type[Any], ids_field: str
) -> Callable[[Node], List[Node]]:
    """
    Returns a resolver for resolving `edges` in `XConnection` types
    """

    def resolve_edge(root: Node) -> List[Node]:
        return get_edges_to_return(
            [
                edge_type(
                    **{
                        f"{get_type_from_id_field_name(ids_field)}_id": id_,
                        "cursor": get_cursor_from_offset(i),
                    }
                )
                for i, id_ in enumerate(getattr(root, ids_field))
            ]
        )

    return resolve_edge


def make_edge_class(class_name: str, node_type: Type[Node], id_field_name: str) -> Type:
    klass = type(
        class_name,
        (),
        {
            "__annotations__": {
                "cursor": str,
                id_field_name: strawberry.Private[str],
                "node": node_type,
            },
            "node": strawberry.field(
                resolver=make_node_resolver(node_type, id_field_name)
            ),
        },
    )
    return klass


def make_connection_class(
    class_name: str, edge_type: Type, ids_field_name: str
) -> Type:
    klass = type(
        class_name,
        (),
        {
            "__annotations__": {
                "page_info": PageInfo,
                ids_field_name: strawberry.Private[List[str]],
                "edges": List[edge_type],
            },
            "edges": strawberry.field(
                resolver=make_edge_resolver(edge_type, ids_field_name)
            ),
        },
    )
    return klass


def make_edge_strawberry_type(
    type_name: str, node_type: Type[Node], id_field_name: str
) -> Type:
    EdgeClass = make_edge_class(
        class_name=type_name, node_type=node_type, id_field_name=id_field_name
    )
    return strawberry.type(EdgeClass)


def make_connection_strawberry_type(
    type_name: str, edge_type: Type[Node], ids_field_name: str
) -> Type:
    ConnectionClass = make_connection_class(
        class_name=type_name,
        edge_type=edge_type,
        ids_field_name=ids_field_name,
    )
    return strawberry.type(ConnectionClass)


def add_to_globals(klass: Type) -> None:
    globals()[klass.__name__] = klass


def plural(noun: str) -> str:
    if noun == "child":
        return "children"
    return noun + "s"


def singular(noun: str) -> str:
    if noun == "children":
        return "child"
    return noun.removesuffix("s")


def generate_types() -> None:
    for model in MODELS.values():
        for field_name in model.__fields__:
            if field_name.endswith("_ids"):
                target_type = field_name.removesuffix("_ids")
                # first generate edge class, since it is required by the connection
                EdgeType = make_edge_strawberry_type(
                    type_name=f"{target_type.title()}Edge",
                    node_type=_NODES[get_type_from_id_field_name(field_name)],
                    id_field_name=singular(field_name),
                )
                add_to_globals(EdgeType)
                # then generate the connection class using the new edge class
                ConnectionType = make_connection_strawberry_type(
                    type_name=f"{target_type.title()}Connection",
                    edge_type=EdgeType,
                    ids_field_name=field_name,
                )
                add_to_globals(ConnectionType)


generate_types()
