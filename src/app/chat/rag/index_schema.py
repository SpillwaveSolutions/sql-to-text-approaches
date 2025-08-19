"""
Schema Indexing for RAG System

This script extracts schema information from the PostgreSQL database,
generates embeddings using sentence transformers, and stores them in
the vector database for semantic search.
"""

import sys
import os
import json
import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from sqlalchemy import text
from src.common.db_utils import get_db_connection
from src.metadata.get_database_ddl import get_database_schema
from src.loadin.create_foreign_keys import find_foreign_key_relationships, create_foreign_keys

class SchemaEmbeddingIndexer:
    """Class for generating and storing schema embeddings"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the schema embedding indexer
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model_name = model_name
        self.model = None
        self.engine = get_db_connection()
        
    def load_model(self):
        """Load the sentence transformer model"""
        print(f"Loading sentence transformer model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        print(f"✓ Model loaded. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
    
    def ensure_foreign_keys(self):
        """Ensure foreign key relationships exist in the PostgreSQL database"""
        print("Ensuring foreign key relationships exist...")
        
        try:
            # Get all tables in the database
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_type = 'BASE TABLE'
                    AND table_schema = 'public'
                """))
                tables = [row[0] for row in result]
            
            # Find and create foreign key relationships
            relationships = find_foreign_key_relationships(self.engine, tables)
            if relationships:
                print(f"Found {len(relationships)} potential foreign key relationships")
                create_foreign_keys(self.engine, relationships)
                print("✓ Foreign key relationships ensured")
            else:
                print("✓ No new foreign key relationships needed")
                
        except Exception as e:
            print(f"Warning: Failed to ensure PostgreSQL foreign keys: {e}")
            print("Continuing with schema indexing...")
        
    def generate_table_context(self, table_info: Dict) -> str:
        """
        Generate rich context text for a table
        
        Args:
            table_info: Table information dictionary
            
        Returns:
            Rich context string for embedding
        """
        context_parts = []
        
        # Table name and basic info
        context_parts.append(f"Table: {table_info['name']}")
        
        # Column information
        columns_desc = []
        for col in table_info['columns']:
            col_desc = f"{col['name']} ({col['data_type']})"
            if not col['is_nullable']:
                col_desc += " NOT NULL"
            if col.get('description'):
                col_desc += f" - {col['description']}"
            columns_desc.append(col_desc)
        
        context_parts.append("Columns: " + ", ".join(columns_desc))
        
        # Primary key
        if table_info.get('primary_key'):
            pk_cols = ", ".join(table_info['primary_key']['columns'])
            context_parts.append(f"Primary Key: {pk_cols}")
        
        # Foreign keys (relationships)
        if table_info.get('foreign_keys'):
            fk_desc = []
            for fk in table_info['foreign_keys']:
                fk_cols = ", ".join(fk['columns'])
                ref_table = fk['references']['table']
                ref_cols = ", ".join(fk['references']['columns'])
                fk_desc.append(f"{fk_cols} -> {ref_table}({ref_cols})")
            context_parts.append("Foreign Keys: " + "; ".join(fk_desc))
        
        return " | ".join(context_parts)
    
    def generate_column_context(self, table_info: Dict, column_info: Dict) -> str:
        """
        Generate rich context text for a column
        
        Args:
            table_info: Table information dictionary
            column_info: Column information dictionary
            
        Returns:
            Rich context string for embedding
        """
        context_parts = []
        
        # Basic column info
        context_parts.append(f"Column: {table_info['name']}.{column_info['name']}")
        context_parts.append(f"Type: {column_info['data_type']}")
        
        # Nullable
        if not column_info['is_nullable']:
            context_parts.append("NOT NULL")
        
        # Description if available
        if column_info.get('description'):
            context_parts.append(f"Description: {column_info['description']}")
        
        # Check if it's part of primary key
        if table_info.get('primary_key') and column_info['name'] in table_info['primary_key']['columns']:
            context_parts.append("PRIMARY KEY")
        
        # Check if it's part of foreign keys
        if table_info.get('foreign_keys'):
            for fk in table_info['foreign_keys']:
                if column_info['name'] in fk['columns']:
                    ref_table = fk['references']['table']
                    context_parts.append(f"FOREIGN KEY -> {ref_table}")
        
        # Add table context for better understanding
        table_columns = [col['name'] for col in table_info['columns']]
        context_parts.append(f"Table context: {table_info['name']} has columns ({', '.join(table_columns)})")
        
        return " | ".join(context_parts)
    
    def clear_existing_embeddings(self):
        """Clear existing embeddings from the database"""
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM schema_embeddings")).fetchone()
            existing_count = result[0] if result else 0
            
            if existing_count > 0:
                print(f"Clearing {existing_count} existing embeddings...")
                conn.execute(text("DELETE FROM schema_embeddings"))
                conn.commit()
                print("✓ Existing embeddings cleared")
            else:
                print("No existing embeddings to clear")
    
    def store_embeddings(self, embeddings_data: List[Dict]):
        """
        Store embeddings in the database
        
        Args:
            embeddings_data: List of dictionaries containing embedding information
        """
        print(f"Storing {len(embeddings_data)} embeddings in database...")
        
        insert_sql = """
        INSERT INTO schema_embeddings (
            schema_name, table_name, column_name, element_type,
            description, full_context, embedding, metadata
        ) VALUES (
            :schema_name, :table_name, :column_name, :element_type,
            :description, :full_context, :embedding, :metadata
        )
        """
        
        with self.engine.connect() as conn:
            for data in tqdm(embeddings_data, desc="Storing embeddings"):
                # Convert numpy array to list for PostgreSQL
                embedding_list = data['embedding'].tolist()
                
                conn.execute(text(insert_sql), {
                    'schema_name': data['schema_name'],
                    'table_name': data['table_name'],
                    'column_name': data.get('column_name'),
                    'element_type': data['element_type'],
                    'description': data.get('description'),
                    'full_context': data['full_context'],
                    'embedding': embedding_list,
                    'metadata': json.dumps(data.get('metadata', {}))
                })
            
            conn.commit()
        
        print("✓ All embeddings stored successfully")
    
    def generate_and_store_embeddings(self, schema_name: str = 'public'):
        """
        Generate embeddings for all schema elements and store them
        
        Args:
            schema_name: Name of the schema to process
        """
        # Get schema information
        print("Extracting database schema...")
        schema = get_database_schema(schema_name)
        
        if not schema['tables']:
            print("No tables found in the schema")
            return
        
        print(f"Found {len(schema['tables'])} tables to process")
        
        # Prepare all contexts for embedding
        contexts = []
        metadata_list = []
        
        for table_info in schema['tables']:
            # Generate table-level context
            table_context = self.generate_table_context(table_info)
            contexts.append(table_context)
            metadata_list.append({
                'schema_name': table_info['schema'],
                'table_name': table_info['name'],
                'column_name': None,
                'element_type': 'table',
                'description': None,  # Tables don't have descriptions in our schema
                'full_context': table_context,
                'metadata': {
                    'column_count': len(table_info['columns']),
                    'has_primary_key': table_info.get('primary_key') is not None,
                    'foreign_key_count': len(table_info.get('foreign_keys', []))
                }
            })
            
            # Generate column-level contexts
            for column_info in table_info['columns']:
                column_context = self.generate_column_context(table_info, column_info)
                contexts.append(column_context)
                metadata_list.append({
                    'schema_name': table_info['schema'],
                    'table_name': table_info['name'],
                    'column_name': column_info['name'],
                    'element_type': 'column',
                    'description': column_info.get('description'),
                    'full_context': column_context,
                    'metadata': {
                        'data_type': column_info['data_type'],
                        'is_nullable': column_info['is_nullable'],
                        'is_primary_key': (
                            table_info.get('primary_key') and 
                            column_info['name'] in table_info['primary_key']['columns']
                        ),
                        'is_foreign_key': any(
                            column_info['name'] in fk['columns'] 
                            for fk in table_info.get('foreign_keys', [])
                        )
                    }
                })
        
        print(f"Generated {len(contexts)} contexts ({len([m for m in metadata_list if m['element_type'] == 'table'])} tables, {len([m for m in metadata_list if m['element_type'] == 'column'])} columns)")
        
        # Generate embeddings
        print("Generating embeddings...")
        embeddings = self.model.encode(contexts, show_progress_bar=True)
        
        # Prepare data for storage
        embeddings_data = []
        for i, (embedding, metadata) in enumerate(zip(embeddings, metadata_list)):
            metadata['embedding'] = embedding
            embeddings_data.append(metadata)
        
        # Store embeddings
        self.store_embeddings(embeddings_data)
    
    def test_similarity_search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Test the similarity search functionality
        
        Args:
            query: Search query
            limit: Number of results to return
            
        Returns:
            List of similar schema elements
        """
        # Generate embedding for query
        query_embedding = self.model.encode([query])[0]
        query_vector = query_embedding.tolist()
        
        # Search for similar embeddings
        search_sql = """
        SELECT 
            schema_name, table_name, column_name, element_type,
            description, full_context, metadata,
            1 - (embedding <=> (:query_vector)::vector) as similarity
        FROM schema_embeddings
        ORDER BY embedding <=> (:query_vector)::vector
        LIMIT :limit
        """
        
        with self.engine.connect() as conn:
            # Convert list to string for PostgreSQL
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'
            results = conn.execute(text(search_sql), {
                'query_vector': vector_str,
                'limit': limit
            }).fetchall()
        
        return [{
            'schema_name': row.schema_name,
            'table_name': row.table_name,
            'column_name': row.column_name,
            'element_type': row.element_type,
            'description': row.description,
            'full_context': row.full_context,
            'metadata': row.metadata if isinstance(row.metadata, dict) else (json.loads(row.metadata) if row.metadata else {}),
            'similarity': float(row.similarity)
        } for row in results]

def main():
    """Main indexing function"""
    print("Starting schema embedding indexing...")
    
    try:
        # Initialize indexer
        indexer = SchemaEmbeddingIndexer()
        
        # Ensure foreign key relationships exist
        print("\nEnsuring foreign key relationships...")
        indexer.ensure_foreign_keys()
        
        # Load the sentence transformer model
        indexer.load_model()
        
        # Clear existing embeddings
        print("\nClearing existing embeddings...")
        indexer.clear_existing_embeddings()
        
        # Generate and store new embeddings
        print("\nGenerating and storing embeddings...")
        indexer.generate_and_store_embeddings()
        
        # Test the search functionality
        print("\nTesting similarity search...")
        test_queries = [
            "customer information",
            "order details",
            "product price",
            "shipping address"
        ]
        
        for query in test_queries:
            print(f"\nQuery: '{query}'")
            results = indexer.test_similarity_search(query, limit=3)
            for i, result in enumerate(results, 1):
                element = f"{result['table_name']}.{result['column_name']}" if result['column_name'] else result['table_name']
                print(f"  {i}. {element} ({result['element_type']}) - Similarity: {result['similarity']:.3f}")
                if result['description']:
                    print(f"     Description: {result['description']}")
        
        print("\n🎉 Schema indexing completed successfully!")
        print("You can now use the RAG chat application for semantic schema search.")
        
    except Exception as e:
        print(f"\n❌ Indexing failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()