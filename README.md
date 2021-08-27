# graphql-python

Just tinkering with GraphQL in Python, I'm liking Strawberry so far. Strawberry Pydantic integration is better, however `strawberry.field`s do not currently work on Pydantic-based types which is a bummer: https://github.com/strawberry-graphql/strawberry/issues/894

## Installation

First install Python 3.9.4, then create a `venv` and run the following:

```bash
pip install -r requirements.txt
cp dev.env .env
```

## Usage

To start the server with hot reloading run `uvicorn berry.app:app --reload`.

You can go to the GraphiQL interface at http://127.0.0.1:8000/graphql

## Development

Install `requirements-dev.txt` too. Run linting with `tox -e lint`
