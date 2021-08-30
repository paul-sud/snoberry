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

# How to pass validation rules to server?
#     validation_rules = default_validation_rules + [depth_limit_validator(10)]
#     result = schema.execute_sync(query, validation_rules=validation_rules)


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
        type_id = self.child_id.split(":")[1]
        table = database.get_table_by_name("children")
        query = table.select().where(table.c.id == type_id)
        row = await database.database.fetch_one(query=query)
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
    async def node(self, id: str) -> Node:
        """
        `node` root field required for Relay (refetching etc)

        Using `construct` skips validation and should be much faster. It's ok because
        we trust that the data in the database was validated at creation/update
        """
        typename, type_id = id.split(":")
        table = database.get_table_by_name(typename)
        # No need for pydantic validation, data in DB is well-formed
        query = table.select().where(table.c.id == type_id)
        row = await database.database.fetch_one(query=query)
        model = cast(BaseModel, MODELS[typename])
        modeled = model.construct(**row.data)
        return _NODES[typename](id=row.id, **modeled.dict())

    @strawberry.field
    async def get_parent(self, id: str) -> Parent:
        typename, type_id = id.split(":")
        table = database.get_table_by_name(typename)
        query = table.select().where(table.c.id == type_id)
        row = await database.database.fetch_one(query=query)
        # No need for pydantic validation, data in DB is well-formed
        parent = ParentModel.construct(**row.data)
        return Parent(id=row.id, **parent.dict())
