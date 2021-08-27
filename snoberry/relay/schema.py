from typing import Optional

import strawberry


@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None


@strawberry.interface
class Node:
    """
    Defining and enforcing the interface in Pydantic makes IDs required when validating,
    as is the case when setting `is_interface=True`
    """

    id: str
