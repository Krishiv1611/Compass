from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import settings

# Create the SQLAlchemy engine
# Neon DB connections should typically use pooling and handle SSL, which are handled via the URL usually.
engine = create_engine(
    settings.sqlalchemy_db_uri,
    pool_pre_ping=True,  # recommended to gracefully handle disconnects
    pool_size=5,
    max_overflow=10
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
