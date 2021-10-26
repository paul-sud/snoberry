# snoberry

## Features
* Supports deep mutations (inspired by [Dgraph](https://dgraph.io/docs/graphql/mutations/deep/))
* Implements [Relay server specification](https://relay.dev/docs/guides/graphql-server-specification/)
* Code-first approach to schema, models written in Pydantic
* Backed by relational storage for ACIDity

## Installation

First install Python 3.9.4, then create a `venv` and run the following:

```bash
pip install -r requirements.txt
cp dev.env .env
```

## Usage

To start the server with hot reloading run `uvicorn snoberry.app:app --reload --reload-dir snoberry`.

You can go to the GraphiQL interface at http://127.0.0.1:8000/graphql

## Development

Install `requirements-dev.txt` too. Run linting with `tox -e lint`

## Todo

* Dataloader: https://strawberry.rocks/docs/guides/dataloaders
* Redis cache in front of DB for ID -> data lookup
* Use Alembic for managing DB
* Use Relay pagination built in to strawberry and/or implement with generics
  * https://github.com/strawberry-graphql/strawberry/issues/175#issuecomment-632037277
  * Example implementation here: https://github.com/strawberry-graphql/strawberry/discussions/535
* Persisted queries
  * https://www.apollographql.com/docs/apollo-server/performance/apq/
  * https://www.envelop.dev/plugins/use-persisted-operations
* Plural identifying root fields if needed, not technically not required for relay
  * https://relay.dev/graphql/objectidentification.htm#sec-Plural-identifying-root-fields
* Permissions: https://strawberry.rocks/docs/guides/permissions
* Use poetry to manage dependencies
* Continuously export traces to Jaeger/whatever
* Containerize

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

### How to configure tracing

From https://gist.github.com/ossareh/15a4c3ccfbf919b2c292b7e91fa6966b

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def configure_tracer(
    service_name: str, agent_host_name: str = "localhost", agent_port: int = 6831
):

    trace.set_tracer_provider(
        TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    )

    trace.get_tracer_provider().add_span_processor(
        # TODO: opentelemetry.sdk.trace.export.BatchSpanProcessor is preferable here
        # however currently it seems to result in spans not being correctly stitched together
        # once they're on the aggregator - this is likely merely a configuration issue
        SimpleSpanProcessor(
            JaegerExporter(agent_host_name=agent_host_name, agent_port=agent_port)
        )
    )

    # required for tracing across RPC boundaries
    set_global_textmap(JaegerPropagator())
```
