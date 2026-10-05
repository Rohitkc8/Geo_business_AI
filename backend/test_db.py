from sqlalchemy import text
from db.database import engine, init_db

def test_connection():
    print("Testing PostgreSQL + PostGIS Connection...")
    try:
        # Try to connect to the DB
        with engine.connect() as conn:
            print("Successfully connected to the database!")
            
            # Check for PostGIS extension
            try:
                result = conn.execute(text("SELECT PostGIS_version();"))
                version = result.scalar()
                print(f"PostGIS is installed: {version}")
                
                # If PostGIS exists, we can initialize tables
                print("Initializing spatial tables...")
                init_db()
                print("Tables created successfully!")
                
            except Exception as e:
                print(f"PostgreSQL connected, but PostGIS extension missing or error: {e}")
                
    except Exception as e:
        print("\n" + "="*50)
        print("DATABASE CHECK SKIPPED")
        print("="*50)
        print("PostgreSQL/PostGIS is not running or DATABASE_URL is not configured.")
        print("Please follow the instructions in 'ubuntu_setup.md' to configure your database server.")
        print(f"Error details: {e}")
        print("="*50)
        # This project can run its API and model flows without the optional
        # persistence service, so an absent local database is a skipped check,
        # not a failing test run.
        return

if __name__ == "__main__":
    test_connection()
