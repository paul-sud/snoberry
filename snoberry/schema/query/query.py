from typing import List, Optional, cast

import strawberry
from pydantic import BaseModel

from ...database import database
from ...models import MODELS, ChildModel, ParentModel
from ...relay.schema import Node, PageInfo
from ...relay.utils import (
    get_cursor_from_offset,
    get_edges_to_return,
    get_start_and_end_cursor,
    has_next_page,
    has_previous_page,
)


@strawberry.experimental.pydantic.type(model=ChildModel, fields=["name"])
class Child(Node):
    pass


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
        # No need for pydantic validation, data in DB is well-formed
        child = ChildModel.construct(**row.data)
        return Child(id=row.id, **child.dict())


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
        model = cast(BaseModel, MODELS[typename])
        modeled = model.construct(**row.data)
        # p: this returns the numerical ID in the table, not the global ID
        return _NODES[typename](id=row.id, **modeled.dict())
