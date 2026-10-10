"""Print the PostgreSQL DDL:  python -m app.database.schema > ../docs/schema.sql"""
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from . import db
from ..models import models  # noqa: F401

if __name__ == "__main__":
    d = postgresql.dialect()
    for t in db.Base.metadata.sorted_tables:
        print(str(CreateTable(t).compile(dialect=d)).strip() + ";")
        for i in sorted(t.indexes, key=lambda i: i.name): print(str(CreateIndex(i).compile(dialect=d)).strip() + ";")
        print()
