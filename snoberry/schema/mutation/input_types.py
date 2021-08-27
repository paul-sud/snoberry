from typing import List, Optional

import strawberry

from ...models import ChildModel, ParentModel


@strawberry.experimental.pydantic.input(model=ChildModel, fields=["name"])
class ChildInput:
    pass


@strawberry.experimental.pydantic.input(model=ParentModel, fields=["name"])
class ParentInput:
    children: Optional[List[ChildInput]] = None
    child_ids: Optional[List[str]] = None
