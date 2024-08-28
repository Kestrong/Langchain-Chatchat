from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import sessionmaker

from configs import SQLALCHEMY_DATABASE_URI, ECHO_SQL

try:
    from configs import DATABASE_SCHEMA
except ImportError:
    DATABASE_SCHEMA = None
import json


def create_engine_wrapper(
        uri=SQLALCHEMY_DATABASE_URI,
        json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
        pool_size=30, pool_recycle=1800, pool_pre_ping=True, pool_timeout=30, echo=ECHO_SQL
):
    return create_engine(
        url=uri, json_serializer=json_serializer, pool_size=pool_size, pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping, pool_timeout=pool_timeout, echo=echo
    )


engine = create_engine_wrapper()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData(
    schema=DATABASE_SCHEMA
)

Base: DeclarativeMeta = declarative_base(metadata=metadata)
