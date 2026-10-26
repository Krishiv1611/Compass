from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import settings

# Create the SQLAlchemy engine
# Neon DB / PostgreSQL connections should use pooling and handle SSL.
# SQLite dialect does not accept pool_size/max_overflow and needs check_same_thread=False for multi-threaded/async.
is_sqlite = settings.sqlalchemy_db_uri.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs = {"pool_pre_ping": True}
if not is_sqlite:
    engine_kwargs.update({"pool_size": 5, "max_overflow": 10})

engine = create_engine(
    settings.sqlalchemy_db_uri,
    connect_args=connect_args,
    **engine_kwargs,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for declarative models
Base = declarative_base()


def get_db():
    """
    Dependency that provides a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
