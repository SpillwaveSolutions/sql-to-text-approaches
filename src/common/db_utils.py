import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def wait_for_postgres(engine, max_attempts=5, delay=2):
    """Wait for PostgreSQL to be ready"""
    for attempt in range(max_attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"Attempt {attempt + 1} failed, retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"Could not connect to PostgreSQL after {max_attempts} attempts")
                raise
    return False

def get_db_connection(database='olist', host='localhost', port=5432, autocommit=False):
    """
    Get database connection properties and create SQLAlchemy engine
    
    Args:
        database (str): Name of the database to connect to. Defaults to 'olist'
        host (str): Database server host. Defaults to 'localhost'
        port (int): Database server port. Defaults to 5432
        autocommit (bool): Whether to use AUTOCOMMIT isolation level. Defaults to False
    
    Returns:
        sqlalchemy.engine.Engine: SQLAlchemy engine instance
    """
    username = 'postgres'
    password = 'YourStrong@Passw0rd'
    
    engine = create_engine(
        f'postgresql://{username}:{password}@{host}:{port}/{database}',
        isolation_level='AUTOCOMMIT' if autocommit else None,
        pool_pre_ping=True  # Add connection health check
    )
    
    # Test the connection
    wait_for_postgres(engine)
    
    return engine
