import asyncio
from typing import List

from pydantic import BaseModel, Field, validator
from typing_extensions import Annotated

from .database import database


async def validate_id(id: str) -> str:
    tablename, item_id = id.split(":")
    table = database.get_table_by_name(tablename)
    query = table.select(1).where(table.c.id == item_id)
    result = await database.database.fetch_one(query=query)
    if result is None:
        raise ValueError(f"ID not in database: {id}")
    return id


def validate_id_sync(id: str) -> str:
    """
    This does not work if there is an event loop already running.
    https://gist.github.com/phizaz/20c36c6734878c6ec053245a477572ec
    """
    return asyncio.get_event_loop().run_until_complete(validate_id(id))


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

    # Validators
    _validate_child_ids = validator(  # type: ignore
        "child_ids", allow_reuse=True, each_item=True
    )(validate_id_sync)


MODELS = {"children": ChildModel, "parents": ParentModel}
database.populate_tables(MODELS)
