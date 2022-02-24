import strawberry

from snoberry.schema.mutation.mutation import get_inner_link_to_type, LinkTo


def test_get_inner_link_to_type_public_link():
    @strawberry.type
    class Foo:
        bar: str

    @strawberry.input
    class Baz:
        foo: LinkTo[Foo]

    result = get_inner_link_to_type(Baz, "foo")
    assert result is Foo


def test_get_inner_link_to_type_public_list_of_links():
    @strawberry.type
    class Foo:
        bar: str

    @strawberry.input
    class Baz:
        foos: list[LinkTo[Foo]]

    result = get_inner_link_to_type(Baz, "foos")
    assert result is Foo
