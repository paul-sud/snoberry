from dataclasses import dataclass
from typing import Generic, List, TypeVar, get_type_hints

from apischema import validator, deserialize

LinkToType = TypeVar("LinkToType")
database = {"1"}


class LinkTo(str, Generic[LinkToType]):
    pass


@validator
def check_linkto(v: LinkTo[LinkToType]) -> None:
    if v not in database:
        raise ValueError(f"Item {v} not in database")


@dataclass
class Bar:
    baz: str


@dataclass
class Foo:
    bar: LinkTo[Bar]
    bars: List[LinkTo[Bar]]


deserialize(Foo, {"bar": "1", "bars": ["1"]})
