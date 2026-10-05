import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Do not hardcode credentials. Load from environment variable.
# Fallback to a placeholder URL if not provided (for demonstration).
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://geouser:password@localhost:5432/geodb")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)
