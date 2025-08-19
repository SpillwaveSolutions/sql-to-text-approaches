import os
import re
from sqlalchemy import text
from src.common.db_utils import get_db_connection
from src.metadata.get_database_ddl import get_database_ddl
from openai import OpenAI
from typing import Dict, List, Tuple

def get_table_columns(engine, table_name: str, schema_name: str = 'public') -> List[Tuple[str, str, bool]]:
    """Get columns and their data types for a table"""
    query = """
    SELECT 
        cols.column_name,
        cols.data_type,
        cols.is_nullable = 'YES' as is_nullable,
        COALESCE(col_description(pgc.oid, cols.ordinal_position), '') as description
    FROM information_schema.columns cols
    LEFT JOIN pg_class pgc ON pgc.relname = cols.table_name
    LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = cols.table_schema
    WHERE cols.table_name = :table_name 
        AND cols.table_schema = :schema_name
    ORDER BY cols.ordinal_position
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {"table_name": table_name, "schema_name": schema_name}).fetchall()
        return [(row[0], row[1], row[2], row[3]) for row in result]

def get_foreign_key_info(engine, table_name: str, schema_name: str = 'public') -> List[Dict]:
    """Get foreign key relationships for a table"""
    query = """
    SELECT 
        tc.constraint_name as fk_name,
        tc.table_name as parent_table,
        kcu.column_name as parent_column,
        ccu.table_name as referenced_table,
        ccu.column_name as referenced_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu 
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
        AND (tc.table_name = :table_name1 OR ccu.table_name = :table_name2)
        AND tc.table_schema = :schema_name
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {"table_name1": table_name, "table_name2": table_name, "schema_name": schema_name}).fetchall()
        return [
            {
                "fk_name": row[0],
                "parent_table": row[1],
                "parent_column": row[2],
                "referenced_table": row[3],
                "referenced_column": row[4]
            }
            for row in result
        ]

def generate_column_description(
    table_name: str,
    column_name: str,
    data_type: str,
    is_nullable: bool,
    fk_info: List[Dict],
    existing_description: str
) -> str:
    """Generate detailed column description using OpenAI"""
    
    # Build context about foreign key relationships
    fk_context = []
    for fk in fk_info:
        if fk["parent_table"] == table_name and fk["parent_column"] == column_name:
            fk_context.append(f"This column is a foreign key referencing {fk['referenced_table']}.{fk['referenced_column']}")
        elif fk["referenced_table"] == table_name and fk["referenced_column"] == column_name:
            fk_context.append(f"This column is referenced by {fk['parent_table']}.{fk['parent_column']}")
    
    fk_context_str = "\n".join(fk_context) if fk_context else "This column has no foreign key relationships."
    
    prompt = f"""Analyze this database column and provide a detailed business description:

Table: {table_name}
Column: {column_name}
Data Type: {data_type}
Nullable: {'Yes' if is_nullable else 'No'}
Foreign Key Information:
{fk_context_str}
Existing Description: {existing_description if existing_description else 'None'}

Please provide a comprehensive description that covers:
1. The business purpose and meaning of this column
2. Its relationship to the overall table entity
3. How it connects to other tables or columns in other tables (if applicable)
4. Any business rules or constraints implied by its data type and nullability
5. Typical use cases for this column in business analysis

Format the response as a concise paragraph suitable for a SQL column description."""

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a database expert who specializes in documenting database schemas with clear, concise, and business-focused descriptions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating description for {table_name}.{column_name}: {str(e)}")
        return existing_description if existing_description else ""

def update_column_description(engine, table_name: str, column_name: str, description: str, schema_name: str = 'public'):
    """Update or add column comment"""
    # Escape single quotes in description
    escaped_description = description.replace("'", "''")
    query = f'COMMENT ON COLUMN "{schema_name}"."{table_name}"."{column_name}" IS :description'
    
    with engine.connect() as conn:
        conn.execute(text(query), {"description": escaped_description})
        conn.commit()

def enrich_metadata(schema_name: str = 'public'):
    """Main function to enrich database metadata with column descriptions"""
    # Ensure OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable must be set")
    
    engine = get_db_connection()
    
    # Get all tables
    table_query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
        AND table_schema = :schema_name
    ORDER BY table_name
    """
    
    with engine.connect() as conn:
        tables = [row[0] for row in conn.execute(text(table_query), {"schema_name": schema_name}).fetchall()]
    
    # Process each table
    for table_name in tables:
        print(f"\nProcessing table: {table_name}")
        
        # Get foreign key information for context
        fk_info = get_foreign_key_info(engine, table_name, schema_name)
        
        # Get columns and their current metadata
        columns = get_table_columns(engine, table_name, schema_name)
        
        # Process each column
        for column_name, data_type, is_nullable, existing_description in columns:
            print(f"  Generating description for column: {column_name}")
            
            # Generate enhanced description
            description = generate_column_description(
                table_name,
                column_name,
                data_type,
                is_nullable,
                fk_info,
                existing_description
            )
            
            # Update the column description in the database
            if description:
                update_column_description(engine, table_name, column_name, description, schema_name)
                print(f"    Updated description for {column_name}")

def main():
    """Main function for CLI usage"""
    enrich_metadata()

if __name__ == "__main__":
    main()
