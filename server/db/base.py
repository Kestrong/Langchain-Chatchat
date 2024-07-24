from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import sessionmaker

from configs import SQLALCHEMY_DATABASE_URI, ECHO_SQL

try:
    from configs import DATABASE_SCHEMA
except ImportError:
    DATABASE_SCHEMA = None
import json

engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    pool_size=30, pool_recycle=1800, pool_pre_ping=True, pool_timeout=30, echo=ECHO_SQL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData(
    schema=DATABASE_SCHEMA
)

Base: DeclarativeMeta = declarative_base(metadata=metadata)
