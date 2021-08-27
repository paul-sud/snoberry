from typing import List, Optional

from pydantic import BaseModel


class PageInfoModel(BaseModel):
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None


class UserModel(BaseModel):
    id: int
    first_name: str
    last_name: str
    friends: List[int]


class NodeModel(BaseModel):
    # Cannot use strawberry.ID here.
    id: str


class ParentModel(NodeModel):
    name: str
    children: "ChildConnectionModel"


class ChildConnectionModel(BaseModel):
    edges: List["ChildEdgeModel"]
    page_info: Optional[PageInfoModel]


class ChildEdgeModel(BaseModel):
    node: "ChildModel"
    cursor: Optional[str]


class ChildModel(NodeModel):
    name: str
