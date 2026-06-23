from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateColumn

from yontai.core.config import get_settings
from yontai.db import models as _models  # noqa: F401
from yontai.db.base import Base

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compatible_schema()


def _ensure_sqlite_compatible_schema() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        for table in Base.metadata.sorted_tables:
            if table.name not in table_names:
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                if not column.nullable and column.default is None and column.server_default is None:
                    continue

                column_ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {column_ddl}'))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


init_db()
