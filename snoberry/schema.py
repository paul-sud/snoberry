from typing import List, Optional

import strawberry
from strawberry.extensions.tracing import ApolloTracingExtension

from .database import database, experiments, files, parents
from .models import (
    ChildConnectionModel,
    ChildEdgeModel,
    ChildModel,
    NodeModel,
    PageInfoModel,
    ParentModel,
    UserModel,
)


def get_files() -> list["File"]:
    return [File(s3_uri="foo", uuid=12)]


async def get_file(uuid: int) -> "File":
    query = files.select().where(files.c.uuid == uuid)
    row = await database.fetch_one(query=query)
    return File(uuid=uuid, **row.data)


@strawberry.type
class File:
    s3_uri: str
    uuid: int
    file_format: Optional[str] = None


@strawberry.input
class FileInput:
    s3_uri: str
    file_format: Optional[str] = None


@strawberry.type
class Experiment:
    uuid: int
    file_ids: strawberry.Private[list[int]]

    @strawberry.field
    async def files(self) -> list[File]:
        return [await get_file(file_id) for file_id in self.file_ids]


@strawberry.input
class ExperimentInput:
    file_ids: list[int]


@strawberry.experimental.pydantic.type(
    model=UserModel, fields=["id", "first_name", "last_name", "friends"]
)
class User:
    """
    Generate schema from Pydantic model.
    """

    @strawberry.field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@strawberry.experimental.pydantic.input(
    model=UserModel, fields=["first_name", "last_name", "friends"]
)
class UserInput:
    """
    user id is not submittable so not exposed in fields.
    """

    pass


@strawberry.experimental.pydantic.type(
    model=NodeModel, fields=["id"], is_interface=True
)
class Node:
    pass


@strawberry.experimental.pydantic.type(
    model=PageInfoModel,
    fields=["has_next_page", "has_previous_page", "start_cursor", "end_cursor"],
)
class PageInfo:
    pass


@strawberry.experimental.pydantic.type(
    model=ChildConnectionModel, fields=["edges", "page_info"]
)
class ChildConnection:
    pass


@strawberry.experimental.pydantic.type(model=ChildEdgeModel, fields=["node", "cursor"])
class ChildEdge:
    pass


@strawberry.experimental.pydantic.type(model=ChildModel, fields=["name", "id"])
class Child:
    pass


@strawberry.experimental.pydantic.type(model=ParentModel, fields=["name", "id"])
class Parent:
    """
    Need to specify children here since resolver must take arguments per Relay spec.
    """

    @strawberry.field
    def children(self, first: strawberry.ID, after: int) -> List[ChildConnection]:
        return self.children


@strawberry.type
class Query:
    files: list[File] = strawberry.field(resolver=get_files)
    get_file: File = strawberry.field(resolver=get_file)

    @strawberry.field
    async def get_experiment(self, uuid: int) -> Experiment:
        query = experiments.select().where(experiments.c.uuid == uuid)
        row = await database.fetch_one(query=query)
        return Experiment(uuid=uuid, **row.data)

    @strawberry.field
    async def get_experiments(self) -> list[Experiment]:
        query = experiments.select()
        rows = await database.fetch_all(query=query)
        return [Experiment(row.uuid, **row.data) for row in rows]

    @strawberry.field
    def get_user(self) -> User:
        return User(id=1, first_name="Mary", last_name="Yram", friends=[1, 2, 3])

    @strawberry.field
    async def get_parents(self) -> List[Parents]:
        query = parents.select()
        rows = await database.fetch_all(query=query)
        return [Parent(id=row.uuid, **row.data) for row in rows]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_file(self, file_input: FileInput) -> int:
        result = await database.execute(
            query=files.insert(),
            values={
                "data": {k: v for k, v in vars(file_input).items() if v is not None}
            },
        )
        return result

    @strawberry.mutation
    async def create_experiment(self, experiment_input: ExperimentInput) -> int:
        result = await database.execute(
            query=experiments.insert(),
            values={
                "data": {
                    k: v for k, v in vars(experiment_input).items() if v is not None
                }
            },
        )
        return result

    @strawberry.mutation
    async def create_parent(self, parent_input: ParentInput) -> int:
        parent_input.to_pydantic()
        result = await database.execute(
            query=parents.insert(), values={"data": vars(parent_input)}
        )
        return result


schema = strawberry.Schema(
    query=Query, mutation=Mutation, extensions=[ApolloTracingExtension]
)
