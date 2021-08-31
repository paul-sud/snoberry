# snoberry

## Features
* Supports deep mutations (inspired by [Dgraph](https://dgraph.io/docs/graphql/mutations/deep/))
* Implements [Relay server specification](https://relay.dev/docs/guides/graphql-server-specification/)
* Code-first approach to data, models written in Pydantic
* Backed by relational storage for ACIDity

## Installation

First install Python 3.9.4, then create a `venv` and run the following:

```bash
pip install -r requirements.txt
cp dev.env .env
```

## Usage

To start the server with hot reloading run `uvicorn snoberry.app:app --reload`.

You can go to the GraphiQL interface at http://127.0.0.1:8000/graphql

## Development

Install `requirements-dev.txt` too. Run linting with `tox -e lint`


## Details

### Mutations

The design of this API for deep mutations is based on Dgraph. Essentially, yoo should be able to pass in a mix of child objects containing info needed to create them, or a child object with an existing ID. You can see examples here:
https://dgraph.io/docs/graphql/mutations/deep/
https://github.com/dgraph-io/dgraph/blob/master/graphql/resolve/add_mutation_test.yaml

Interestingly, in one of the examples that adds a new author with two existing posts, the existing posts are detached from their current author, if I understand correctly. I think posts are only allowed to have one author? It seems it should raise an error, as for many use cases this side-effect is undesirable.
https://github.com/dgraph-io/dgraph/blob/master/graphql/resolve/add_mutation_test.yaml#L2029

### Validation

To validate links it would be really nice to not have them just be `str` in the Pydantic model. Something like `LinkTo[File]` would be ideal, where `LinkTo` is a generic class parametrized by the type of link. Then for this type we can define our own custom validation. For details on the custom validation see the following:
https://pydantic-docs.helpmanual.io/usage/types/#classes-with-__get_validators__
https://pydantic-docs.helpmanual.io/usage/types/#generic-classes-as-types

Unfortunately to validate links to other objects, it is not possible to use a generic subclass of `str`. I get `value is not a valid sequence (type=type_error.sequence)`. Below are related issues:
https://github.com/samuelcolvin/pydantic/issues/2264
https://github.com/samuelcolvin/pydantic/issues/2598#issuecomment-839715287 (solution below is based on this comment)

```python
from typing import Any, Generic, List, TypeVar
from pydantic import BaseModel, validator

LinkToType = TypeVar("LinkToType")
database = {"1"}

class LinkTo(str, Generic[LinkToType]):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        if v not in database:
            raise ValueError(f"Item {v} not in database")
        return v

class Bar(BaseModel):
    baz: str

class LinkToBar(LinkTo[Bar]):
    pass

class Foo(BaseModel):
    bar_ids: List[LinkToBar]

f = Foo(bar_ids=["1", "2"])
```
