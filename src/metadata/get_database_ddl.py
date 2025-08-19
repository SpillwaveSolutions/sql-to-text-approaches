"""
This module provides functions to generate DDL (Data Definition Language) scripts
for PostgreSQL database objects.
"""

from sqlalchemy import text
from typing import Dict, List, Optional
from common.db_utils import get_db_connection

def get_table_ddl(engine, table_name, schema_name='public'):
    """Get the DDL for a specific table"""
    ddl_parts = []
    
    # Get column definitions
    column_query = """
    SELECT 
        column_name,
        data_type,
        character_maximum_length,
        numeric_precision,
        numeric_scale,
        is_nullable,
        column_default
    FROM information_schema.columns
    WHERE table_name = %s 
        AND table_schema = %s
    ORDER BY ordinal_position
    """
    
    with engine.connect() as conn:
        columns = conn.execute(text(column_query), (table_name, schema_name)).fetchall()
        
        if not columns:
            return ""
        
        # Build CREATE TABLE statement
        ddl_parts.append(f'CREATE TABLE "{schema_name}"."{table_name}" (')
        
        column_definitions = []
        for col in columns:
            col_def = f'    "{col.column_name}" {format_column_type(col)}'
            
            if col.column_default is not None:
                col_def += f' DEFAULT {col.column_default}'
            
            if col.is_nullable == 'NO':
                col_def += ' NOT NULL'
            
            column_definitions.append(col_def)
        
        # Add primary key constraint
        pk_columns = get_primary_key_columns(engine, table_name, schema_name)
        if pk_columns:
            pk_def = f'    CONSTRAINT "{table_name}_pkey" PRIMARY KEY ({", ".join([f\'"{col}"\' for col in pk_columns])})'
            column_definitions.append(pk_def)
        
        ddl_parts.append(',\n'.join(column_definitions))
        ddl_parts.append(');')
    
    # Get and add column comments
    comments = get_column_comments(engine, table_name, schema_name)
    if comments:
        ddl_parts.append("\n-- Column Comments")
        for column_name, comment in comments:
            # Escape single quotes in comment
            comment = comment.replace("'", "''")
            ddl_parts.append(f"COMMENT ON COLUMN \"{schema_name}\".\"{table_name}\".\"{column_name}\" IS '{comment}';")
    
    return "\n".join(ddl_parts)

def format_column_type(col):
    """Format PostgreSQL column type with precision/scale/length"""
    data_type = col.data_type.upper()
    
    if data_type in ('CHARACTER VARYING', 'VARCHAR'):
        if col.character_maximum_length:
            return f'VARCHAR({col.character_maximum_length})'
        else:
            return 'VARCHAR'
    elif data_type in ('CHARACTER', 'CHAR'):
        if col.character_maximum_length:
            return f'CHAR({col.character_maximum_length})'
        else:
            return 'CHAR'
    elif data_type == 'TEXT':
        return 'TEXT'
    elif data_type in ('NUMERIC', 'DECIMAL'):
        if col.numeric_precision and col.numeric_scale is not None:
            return f'NUMERIC({col.numeric_precision},{col.numeric_scale})'
        elif col.numeric_precision:
            return f'NUMERIC({col.numeric_precision})'
        else:
            return 'NUMERIC'
    elif data_type == 'INTEGER':
        return 'INTEGER'
    elif data_type == 'BIGINT':
        return 'BIGINT'
    elif data_type == 'SMALLINT':
        return 'SMALLINT'
    elif data_type == 'BOOLEAN':
        return 'BOOLEAN'
    elif data_type == 'TIMESTAMP WITHOUT TIME ZONE':
        return 'TIMESTAMP'
    elif data_type == 'TIMESTAMP WITH TIME ZONE':
        return 'TIMESTAMPTZ'
    elif data_type == 'DATE':
        return 'DATE'
    elif data_type == 'TIME WITHOUT TIME ZONE':
        return 'TIME'
    elif data_type == 'DOUBLE PRECISION':
        return 'DOUBLE PRECISION'
    elif data_type == 'REAL':
        return 'REAL'
    else:
        return data_type

def get_column_comments(engine, table_name, schema_name='public'):
    """Get comments for all columns in a table"""
    query = """
    SELECT 
        cols.column_name,
        col_description(pgc.oid, cols.ordinal_position) as comment
    FROM information_schema.columns cols
    JOIN pg_class pgc ON pgc.relname = cols.table_name
    JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace
    WHERE cols.table_name = %s 
        AND cols.table_schema = %s
        AND pgn.nspname = %s
        AND col_description(pgc.oid, cols.ordinal_position) IS NOT NULL
    ORDER BY cols.ordinal_position
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), (table_name, schema_name, schema_name)).fetchall()
        return [(row.column_name, row.comment) for row in result]

def get_primary_key_columns(engine, table_name, schema_name='public'):
    """Get primary key columns for a table"""
    query = """
    SELECT c.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage c 
        ON c.constraint_name = tc.constraint_name
        AND c.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_name = %s
        AND tc.table_schema = %s
    ORDER BY c.ordinal_position
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), (table_name, schema_name)).fetchall()
        return [row.column_name for row in result]

def get_foreign_key_ddl(engine, table_name, schema_name='public'):
    """Get the DDL for foreign keys of a specific table"""
    query = """
    SELECT
        tc.constraint_name,
        string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns,
        ccu.table_schema as foreign_table_schema,
        ccu.table_name as foreign_table_name,
        string_agg(ccu.column_name, ', ' ORDER BY kcu.ordinal_position) as foreign_columns
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu 
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_name = %s
        AND tc.table_schema = %s
    GROUP BY tc.constraint_name, ccu.table_schema, ccu.table_name
    """
    
    ddl_parts = []
    with engine.connect() as conn:
        result = conn.execute(text(query), (table_name, schema_name)).fetchall()
        for row in result:
            fk_ddl = (f'ALTER TABLE "{schema_name}"."{table_name}" '
                     f'ADD CONSTRAINT "{row.constraint_name}" '
                     f'FOREIGN KEY ({row.columns}) '
                     f'REFERENCES "{row.foreign_table_schema}"."{row.foreign_table_name}" ({row.foreign_columns});')
            ddl_parts.append(fk_ddl)
    
    return '\n'.join(ddl_parts)

def get_index_ddl(engine, table_name, schema_name='public'):
    """Get the DDL for indexes of a specific table"""
    query = """
    SELECT
        i.relname as index_name,
        ix.indisunique,
        string_agg(a.attname, ', ' ORDER BY array_position(ix.indkey, a.attnum)) as columns
    FROM pg_class t
    JOIN pg_index ix ON t.oid = ix.indrelid
    JOIN pg_class i ON i.oid = ix.indexrelid
    JOIN pg_attribute a ON t.oid = a.attrelid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    WHERE t.relname = %s
        AND n.nspname = %s
        AND a.attnum = ANY(ix.indkey)
        AND ix.indisprimary = false
    GROUP BY i.relname, ix.indisunique
    """
    
    ddl_parts = []
    with engine.connect() as conn:
        result = conn.execute(text(query), (table_name, schema_name)).fetchall()
        for row in result:
            unique_clause = 'UNIQUE ' if row.indisunique else ''
            index_ddl = (f'CREATE {unique_clause}INDEX "{row.index_name}" '
                        f'ON "{schema_name}"."{table_name}" ({row.columns});')
            ddl_parts.append(index_ddl)
    
    return '\n'.join(ddl_parts)

def get_database_ddl(schema_name='public'):
    """
    Generate DDL for the entire database
    
    Args:
        schema_name (str): Schema name to generate DDL for. Defaults to 'public'
    
    Returns:
        str: Complete DDL script for the database
    """
    engine = get_db_connection()
    ddl_parts = []

    # Get all tables
    table_query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
        AND table_schema = %s
    ORDER BY table_name
    """
    
    with engine.connect() as conn:
        tables = [row.table_name for row in conn.execute(text(table_query), (schema_name,)).fetchall()]
    
    # Generate DDL for each table
    for table_name in tables:
        # Table definition
        table_ddl = get_table_ddl(engine, table_name, schema_name)
        if table_ddl:
            ddl_parts.append(f"-- Table: {table_name}")
            ddl_parts.append(table_ddl)
            ddl_parts.append("")
        
        # Indexes
        index_ddl = get_index_ddl(engine, table_name, schema_name)
        if index_ddl:
            ddl_parts.append(f"-- Indexes for: {table_name}")
            ddl_parts.append(index_ddl)
            ddl_parts.append("")
    
    # Add foreign keys at the end
    for table_name in tables:
        fk_ddl = get_foreign_key_ddl(engine, table_name, schema_name)
        if fk_ddl:
            ddl_parts.append(f"-- Foreign Keys for: {table_name}")
            ddl_parts.append(fk_ddl)
            ddl_parts.append("")
    
    return '\n'.join(ddl_parts)

def get_database_schema(schema_name='public') -> Dict:
    """
    Get a structured representation of the database schema
    
    Args:
        schema_name (str): Schema name to extract. Defaults to 'public'
    
    Returns:
        Dict: A dictionary containing the complete database schema structure:
        {
            'tables': [
                {
                    'schema': str,
                    'name': str,
                    'columns': [
                        {
                            'name': str,
                            'data_type': str,
                            'is_nullable': bool,
                            'description': Optional[str]
                        }
                    ],
                    'primary_key': {
                        'name': str,
                        'columns': List[str]
                    },
                    'foreign_keys': [
                        {
                            'name': str,
                            'columns': List[str],
                            'references': {
                                'schema': str,
                                'table': str,
                                'columns': List[str]
                            }
                        }
                    ]
                }
            ]
        }
    """
    engine = get_db_connection()
    schema = {'tables': []}
    
    # Get all tables
    table_query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE'
        AND table_schema = %s
    ORDER BY table_name
    """
    
    with engine.connect() as conn:
        tables = conn.execute(text(table_query), (schema_name,)).fetchall()
        
        for table in tables:
            table_info = {
                'schema': schema_name,
                'name': table.table_name,
                'columns': [],
                'primary_key': None,
                'foreign_keys': []
            }
            
            # Get columns
            column_query = """
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default,
                col_description(pgc.oid, ordinal_position) as description
            FROM information_schema.columns cols
            LEFT JOIN pg_class pgc ON pgc.relname = cols.table_name
            LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = cols.table_schema
            WHERE table_name = %s 
                AND table_schema = %s
            ORDER BY ordinal_position
            """
            
            columns = conn.execute(text(column_query), (table.table_name, schema_name)).fetchall()
            for col in columns:
                table_info['columns'].append({
                    'name': col.column_name,
                    'data_type': format_column_type(col),
                    'is_nullable': col.is_nullable == 'YES',
                    'description': col.description
                })
            
            # Get primary key
            pk_columns = get_primary_key_columns(engine, table.table_name, schema_name)
            if pk_columns:
                table_info['primary_key'] = {
                    'name': f"{table.table_name}_pkey",
                    'columns': pk_columns
                }
            
            # Get foreign keys
            fk_query = """
            SELECT
                tc.constraint_name,
                string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as columns,
                ccu.table_schema as foreign_table_schema,
                ccu.table_name as foreign_table_name,
                string_agg(ccu.column_name, ',' ORDER BY kcu.ordinal_position) as foreign_columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu 
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
                AND tc.table_schema = %s
            GROUP BY tc.constraint_name, ccu.table_schema, ccu.table_name
            """
            
            fk_results = conn.execute(text(fk_query), (table.table_name, schema_name)).fetchall()
            
            for fk in fk_results:
                table_info['foreign_keys'].append({
                    'name': fk.constraint_name,
                    'columns': fk.columns.split(','),
                    'references': {
                        'schema': fk.foreign_table_schema,
                        'table': fk.foreign_table_name,
                        'columns': fk.foreign_columns.split(',')
                    }
                })
            
            schema['tables'].append(table_info)
    
    return schema

def main():
    """Main function for CLI usage"""
    # Print both DDL and schema for testing
    print("=== DDL Output ===")
    ddl = get_database_ddl()
    print(ddl)
    
    print("\n=== Schema Output ===")
    schema = get_database_schema()
    for table in schema['tables']:
        print(f"\nTable: {table['schema']}.{table['name']}")
        print("Columns:")
        for col in table['columns']:
            nullable = 'NULL' if col['is_nullable'] else 'NOT NULL'
            print(f"  - {col['name']} {col['data_type']} {nullable}")
            if col['description']:
                print(f"    Description: {col['description']}")
        if table['primary_key']:
            print("Primary Key:")
            print(f"  {table['primary_key']['name']}: {', '.join(table['primary_key']['columns'])}")
        if table['foreign_keys']:
            print("Foreign Keys:")
            for fk in table['foreign_keys']:
                print(f"  {fk['name']}: ({', '.join(fk['columns'])}) -> "
                      f"{fk['references']['schema']}.{fk['references']['table']}({', '.join(fk['references']['columns'])})")

if __name__ == "__main__":
    main()