from typing import Annotated, List

from pydantic import BaseModel, Field

from .database import database


class ChildModel(BaseModel):
    name: str


class ParentModel(BaseModel):
    name: str
    # conlist also works but errors in mypy
    child_ids: Annotated[List[str], Field(min_items=1)]


MODELS = {"children": ChildModel, "parents": ParentModel}
database.populate_tables(MODELS)
