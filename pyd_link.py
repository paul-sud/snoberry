from pydantic import BaseModel, validator
from typing import Any, List, TypeVar, Generic


LinkToType = TypeVar('LinkToType')

database = {"1"}


class LinkTo(str, Generic[LinkToType]):
    """
    Based on
    https://pydantic-docs.helpmanual.io/usage/types/#classes-with-__get_validators__
    https://pydantic-docs.helpmanual.io/usage/types/#generic-classes-as-types
    """
    @classmethod
    def __get_validators__(cls):
        """
        One or more validators may be yielded which will be called in the yielded order
        to validate the input. Each validator will receive as an input the value
        returned from the previous validator
        """
        yield cls.validate

    @classmethod
    def validate(cls, v):
        # you could also return a string here which would mean model.post_code
        # would be a string, pydantic won't care but you could end up with some
        # confusion since the value's type won't match the type annotation
        # exactly
        # return cls(f'{m.group(1)} {m.group(2)}')
        if not isinstance(v, str):
            raise TypeError('string required')
        if v not in database:
            raise ValueError(f'Item {v} not in database')
        return v


class Bar(BaseModel):
    baz: str


class LinkToBar(LinkTo[Bar]):
    """
    Doesn't work without introducing this extra class:
    https://github.com/samuelcolvin/pydantic/issues/2264

    This solution taken from
    https://github.com/samuelcolvin/pydantic/issues/2598#issuecomment-839715287

    pydantic.error_wrappers.ValidationError: 2 validation errors for Foo
    bar_ids -> 0
      value is not a valid sequence (type=type_error.sequence)
    bar_ids -> 1
      value is not a valid sequence (type=type_error.sequence)
    """
    pass


class Foo(BaseModel):
    bar_ids: List[LinkToBar]


f = Foo(bar_ids=["1", "2"])
