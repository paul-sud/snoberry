"""
`strawberry.tools.create_type` doesn't work for fields that don't have resolvers.
So we first dynamically create the class with `type`, making sure to populate
`__annotations__`, then wrap the class in `strawberry.type`, and finally expose the
generated types in this module by patching `globals()`
"""

from typing import Callable, List, Type

import strawberry

from snoberry.models import MODELS
from snoberry.relay.schema import Node, PageInfo
from snoberry.relay.utils import get_cursor_from_offset, get_edges_to_return
from snoberry.schema.mutation.mutation import get_type_from_id_field_name
from snoberry.schema.query.query import _NODES


def make_node_resolver(node_type: Type, id_field: str) -> Callable:
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


def make_edge_resolver(edge_type: Type, ids_field: str) -> Callable:
    """
    Returns a resolver for resolving `edges` in `XConnection` types
    """

    def resolve_edge(root: Node) -> Node:
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


# # These should be the outputs of the generation step
# @strawberry.type
# class ChildEdge:
#     cursor: str
#     child_id: strawberry.Private[str]
#     node: Child = strawberry.field(resolver=get_node)


# @strawberry.type
# class ChildConnection:
#     page_info: PageInfo
#     child_ids: strawberry.Private[List[str]]

#     @strawberry.field
#     def edges(self) -> List[ChildEdge]:
#         return get_edges_to_return(
#             [
#                 ChildEdge(child_id=child_id, cursor=get_cursor_from_offset(i))
#                 for i, child_id in enumerate(self.child_ids)
#             ]
#         )


def make_edge_class(class_name: str, node_type: Node, id_field_name: str) -> Type:
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
    type_name: str, node_type: Node, id_field_name: str
) -> Type:
    EdgeClass = make_edge_class(
        class_name=f"{type_name}Class", node_type=node_type, id_field_name=id_field_name
    )
    return strawberry.type(EdgeClass)


def make_connection_strawberry_type(
    type_name: str, edge_type: Type, ids_field_name: str
) -> Type:
    ConnectionClass = make_connection_class(
        class_name=f"{type_name}Class",
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


for model_name, model in MODELS.items():
    edge_fields = []
    connection_fields = []
    for field_name, field in vars(model).items():
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
