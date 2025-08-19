"""
Setup script for pgvector extension and schema embeddings table.
This script initializes the database with the necessary extensions and tables
for storing schema information embeddings.
"""

import sys
import os

from sqlalchemy import text, create_engine
from src.common.db_utils import get_db_connection
from src.loadin.create_foreign_keys import find_foreign_key_relationships, create_foreign_keys

def setup_foreign_keys():
    """Create foreign key relationships in the PostgreSQL database"""
    print("Creating foreign key relationships...")
    
    try:
        # Get PostgreSQL database connection
        engine = get_db_connection()
        
        # Get all tables in the database
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_type = 'BASE TABLE'
                AND table_schema = 'public'
            """))
            tables = [row[0] for row in result]
        
        print(f"Found {len(tables)} tables in PostgreSQL database")
        
        # Find and create foreign key relationships
        relationships = find_foreign_key_relationships(engine, tables)
        if relationships:
            print(f"Found {len(relationships)} potential foreign key relationships")
            create_foreign_keys(engine, relationships)
            print("✓ Foreign key creation completed successfully")
        else:
            print("✓ No new foreign key relationships found")
            
    except Exception as e:
        print(f"Warning: Failed to create PostgreSQL foreign keys: {e}")
        print("Continuing with RAG setup...")

def setup_pgvector_extension():
    """Install pgvector extension in the database"""
    engine = get_db_connection()
    
    with engine.connect() as conn:
        # Enable pgvector extension
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            print("✓ pgvector extension enabled successfully")
        except Exception as e:
            print(f"Error enabling pgvector extension: {e}")
            raise

def create_schema_embeddings_table():
    """Create table for storing schema element embeddings"""
    engine = get_db_connection()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS schema_embeddings (
        id SERIAL PRIMARY KEY,
        schema_name VARCHAR(255) NOT NULL DEFAULT 'public',
        table_name VARCHAR(255) NOT NULL,
        column_name VARCHAR(255),
        element_type VARCHAR(50) NOT NULL, -- 'table' or 'column'
        description TEXT,
        full_context TEXT NOT NULL, -- Complete context for embedding
        embedding vector(384), -- Using sentence-transformers all-MiniLM-L6-v2 dimension
        metadata JSONB, -- Additional metadata about the schema element
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    create_indexes_sql = [
        # Vector similarity index using HNSW
        "CREATE INDEX IF NOT EXISTS idx_schema_embeddings_vector ON schema_embeddings USING hnsw (embedding vector_cosine_ops);",
        
        # Regular indexes for efficient filtering
        "CREATE INDEX IF NOT EXISTS idx_schema_embeddings_table ON schema_embeddings (table_name);",
        "CREATE INDEX IF NOT EXISTS idx_schema_embeddings_element_type ON schema_embeddings (element_type);",
        "CREATE INDEX IF NOT EXISTS idx_schema_embeddings_schema_table ON schema_embeddings (schema_name, table_name);",
    ]
    
    with engine.connect() as conn:
        try:
            # Create the main table
            conn.execute(text(create_table_sql))
            print("✓ schema_embeddings table created successfully")
            
            # Create indexes
            for index_sql in create_indexes_sql:
                conn.execute(text(index_sql))
            print("✓ Vector and regular indexes created successfully")
            
            conn.commit()
            
        except Exception as e:
            print(f"Error creating schema embeddings table: {e}")
            raise

def create_update_trigger():
    """Create trigger to automatically update updated_at timestamp"""
    engine = get_db_connection()
    
    trigger_sql = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    
    DROP TRIGGER IF EXISTS update_schema_embeddings_updated_at ON schema_embeddings;
    
    CREATE TRIGGER update_schema_embeddings_updated_at
        BEFORE UPDATE ON schema_embeddings
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """
    
    with engine.connect() as conn:
        try:
            conn.execute(text(trigger_sql))
            conn.commit()
            print("✓ Updated timestamp trigger created successfully")
        except Exception as e:
            print(f"Error creating update trigger: {e}")
            raise

def verify_setup():
    """Verify that the setup was successful"""
    engine = get_db_connection()
    
    with engine.connect() as conn:
        # Check if pgvector extension is installed
        result = conn.execute(text("SELECT name FROM pg_available_extensions WHERE name = 'vector' AND installed_version IS NOT NULL;")).fetchone()
        if result:
            print("✓ pgvector extension is properly installed")
        else:
            print("✗ pgvector extension is not installed")
            return False
        
        # Check if schema_embeddings table exists
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name = 'schema_embeddings' AND table_schema = 'public';")).fetchone()
        if result:
            print("✓ schema_embeddings table exists")
        else:
            print("✗ schema_embeddings table does not exist")
            return False
        
        # Check if vector index exists
        result = conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'schema_embeddings' AND indexname = 'idx_schema_embeddings_vector';")).fetchone()
        if result:
            print("✓ Vector similarity index exists")
        else:
            print("✗ Vector similarity index does not exist")
            return False
    
    return True

def main():
    """Main setup function"""
    print("Setting up pgvector and schema embeddings...")
    
    try:
        # Step 1: Create foreign key relationships
        print("\n1. Creating foreign key relationships...")
        setup_foreign_keys()
        
        # Step 2: Enable pgvector extension
        print("\n2. Enabling pgvector extension...")
        setup_pgvector_extension()
        
        # Step 3: Create schema embeddings table
        print("\n3. Creating schema embeddings table...")
        create_schema_embeddings_table()
        
        # Step 4: Create update trigger
        print("\n4. Creating update timestamp trigger...")
        create_update_trigger()
        
        # Step 5: Verify setup
        print("\n5. Verifying setup...")
        if verify_setup():
            print("\n🎉 Setup completed successfully!")
            print("\nYou can now run the schema indexing script to populate embeddings.")
        else:
            print("\n❌ Setup verification failed. Please check the errors above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()