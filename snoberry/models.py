from typing import List

from pydantic import BaseModel, Field, validator
from typing_extensions import Annotated

from .database import database


class ChildModel(BaseModel):
    name: str


class ParentModel(BaseModel):
    """
    Would be nice to attach validators to the model functionally, but it's not possible.
    See https://github.com/samuelcolvin/pydantic/issues/2076

    Instead we just use the resuse validators to verify IDs
    https://pydantic-docs.helpmanual.io/usage/validators/#reuse-validators

    May be worth implementing as a root validator checking all `_id/_ids` fields.
    """

    name: str
    # conlist also works but errors in mypy
    child_ids: Annotated[List[str], Field(min_items=1)]


MODELS = {"children": ChildModel, "parents": ParentModel}
database.populate_tables(MODELS)
