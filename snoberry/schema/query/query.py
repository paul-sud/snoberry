from dataclasses import field
from typing import List, Optional
from typing_extensions import Protocol

import strawberry
from apischema import schema

from ...database import database
from ...relay.schema import Node, PageInfo
from ...relay.utils import (
    get_cursor_from_offset,
    get_edges_to_return,
    get_start_and_end_cursor,
    has_next_page,
    has_previous_page,
)


class HasTableName(Protocol):
    def table_name(self) -> None:
        ...


@strawberry.type
class Child(Node):
    name: str

    @property
    def table_name(self) -> str:
        return "children"


@strawberry.type
class ChildEdge:
    cursor: str
    child_id: strawberry.Private[str]

    @strawberry.field
    async def node(self) -> Child:
        """
        Identical code to other resolvers
        """
        row = await database.get_by_guid(self.child_id)
        return Child(id=row.id, **row.data)


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


@strawberry.type
class Parent(Node):
    """
    Need to specify children here since resolver must take arguments per Relay spec.
    """
    name: str
    child_ids: strawberry.Private[List[str]] = field(
        default_factory=list,
        metadata=schema(max_items=1, unique=True),
    )

    @strawberry.field
    def children(
        self, first: Optional[int] = None, after: Optional[str] = None
    ) -> ChildConnection:
        """
        page_info not resolved on ChildConnection because we need access to first and
        after. They could be stored
        """
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


_NODES = {"parents": Parent, "children": Child}


@strawberry.type
class Query:
    @strawberry.field
    async def node(self, id: str) -> Node:
        """
        `node` root field required for Relay (refetching etc)

        Using `construct` skips validation and should be much faster. It's ok because
        we trust that the data in the database was validated at creation/update
        """
        typename, _ = id.split(":")
        row = await database.get_by_guid(id)
        return _NODES[typename](id=row.id, **row.data)
