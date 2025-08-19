# RAG-Based Database Chat System

A Retrieval-Augmented Generation (RAG) system that uses PostgreSQL's pgvector extension for semantic search of database schema information. 
Instead of providing the entire database schema to the language model, this system dynamically retrieves only the most relevant tables and 
columns based on semantic similarity to the user's question.

## Overview

This RAG implementation addresses the limitations of the "full-schema-in-prompt" approach used in the plain_llm version:

- **Scalability**: Works with large database schemas without hitting token limits
- **Relevance**: Only retrieves schema elements relevant to the user's question
- **Performance**: Faster query generation due to focused schema context
- **Accuracy**: More precise SQL generation by providing targeted schema information

## Architecture

The system consists of three main components:

1. **Schema Indexing**: Extracts database schema, generates embeddings, and stores them in pgvector
2. **Semantic Retrieval**: Uses sentence transformers to find relevant schema elements
3. **SQL Generation**: Uses retrieved schema context to generate precise SQL queries

## Key Features

- 🔍 **Semantic Schema Search**: Finds relevant tables and columns using vector similarity
- 🚀 **Scalable**: Handles large database schemas efficiently
- 🎯 **Context-Aware**: Provides only relevant schema information to the LLM
- 🤖 **LLM-Generated Database Summary**: Intelligent analysis of database structure and purpose
- 🔧 **Self-Correction System**: Automatically retries failed queries with expanded context (up to 3 attempts)
- 📊 **Visual Analytics**: Automatic visualization of query results
- 💬 **Chat Interface**: User-friendly Streamlit-based conversational interface
- 🔄 **Real-time**: Dynamic schema retrieval for each query

## Installation and Setup

### Option 1: Automated Setup (Recommended)

```bash
# Install RAG-specific dependencies
poetry install --with chat,rag

# Run the complete setup (includes foreign keys, pgvector, and schema indexing)
export OPENAI_API_KEY=your-openai-api-key
./src/app/chat/rag/run_rag_setup.sh
```

The automated setup script will:
1. **Create foreign key relationships** for data integrity (same as `run_data_importer.sh`)
2. **Set up pgvector extension** and schema embeddings table
3. **Generate and store schema embeddings** using sentence-transformers
4. **Test the similarity search** functionality

### Option 2: Manual Setup (Step by Step)

#### 1. Install Dependencies

```bash
# Install RAG-specific dependencies
poetry install --with chat,rag
```

#### 2. Create Foreign Key Relationships

```bash
# Create foreign key relationships (ensures data integrity)
poetry run create-fks
```

#### 3. Set up pgvector Extension

```bash
# Set up the database schema and pgvector extension
poetry run python src/app/chat/rag/setup_vector_db.py
```

This script will:
- Create foreign key relationships in PostgreSQL
- Enable the pgvector extension in PostgreSQL
- Create the `schema_embeddings` table
- Set up vector indexes for fast similarity search
- Create necessary triggers and functions

#### 4. Index Database Schema

```bash
# Generate and store embeddings for your database schema
export OPENAI_API_KEY=your-openai-api-key
poetry run python src/app/chat/rag/index_schema.py
```

This script will:
- Ensure foreign key relationships exist
- Extract schema information from your PostgreSQL database
- Generate embeddings using sentence-transformers
- Store embeddings in the vector database
- Test the similarity search functionality

### 3. Run the Chat Application

```bash
# Start the RAG chat application (auto-initializes if needed)
export OPENAI_API_KEY=your-openai-api-key
poetry run streamlit run src/app/chat/rag/rag_chat_app.py
```

**Note**: The chat application now includes auto-initialization! If the RAG system hasn't been set up, it will automatically run the complete setup process when you first access it.

## How It Works

### Schema Embedding Process

1. **Schema Extraction**: The system extracts detailed information about tables and columns from PostgreSQL's information_schema
2. **Context Generation**: Creates rich context descriptions for each schema element:
   - **Tables**: Includes column names, types, relationships, constraints
   - **Columns**: Includes data types, nullability, relationships, business descriptions
3. **Embedding Generation**: Uses sentence-transformers (all-MiniLM-L6-v2) to generate 384-dimensional embeddings
4. **Vector Storage**: Stores embeddings in PostgreSQL using pgvector with HNSW indexes for fast similarity search

### Query Processing Pipeline

1. **User Input**: User asks a natural language question
2. **Query Embedding**: Generate embedding for the user's question
3. **Semantic Retrieval**: Find most similar schema elements using cosine similarity
4. **Context Formation**: Format retrieved schema elements into structured context
5. **SQL Generation**: Use OpenAI GPT-4 with targeted schema context to generate SQL
6. **Execution & Analysis**: Execute query and provide insights

### Example Retrieval Flow

**User Question**: "Show me customer orders from last month"

**Retrieved Schema Elements**:
```
Table: customers (Relevance: 0.856)
Relevant Columns:
  - customer_id (integer) PRIMARY KEY
  - customer_name (varchar) - Customer full name
  - email (varchar) - Customer email address

Table: orders (Relevance: 0.923) 
Relevant Columns:
  - order_id (integer) PRIMARY KEY
  - customer_id (integer) FOREIGN KEY -> customers
  - order_date (timestamp) - When the order was placed
  - total_amount (numeric) - Total order value
```

**Generated SQL**:
```sql
SELECT c.customer_name, o.order_id, o.order_date, o.total_amount
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id  
WHERE o.order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
  AND o.order_date < DATE_TRUNC('month', CURRENT_DATE)
ORDER BY o.order_date DESC
LIMIT 10;
```

## Technical Implementation

### Database Schema

The system uses a dedicated table to store schema embeddings:

```sql
CREATE TABLE schema_embeddings (
    id SERIAL PRIMARY KEY,
    schema_name VARCHAR(255) NOT NULL DEFAULT 'public',
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255),
    element_type VARCHAR(50) NOT NULL, -- 'table' or 'column'
    description TEXT,
    full_context TEXT NOT NULL, -- Complete context for embedding
    embedding vector(384), -- sentence-transformers dimension
    metadata JSONB, -- Additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index using HNSW
CREATE INDEX idx_schema_embeddings_vector 
ON schema_embeddings USING hnsw (embedding vector_cosine_ops);
```

### Embedding Model

- **Model**: `all-MiniLM-L6-v2` from sentence-transformers
- **Dimension**: 384
- **Similarity Metric**: Cosine similarity
- **Performance**: Fast inference, good semantic understanding

### Retrieval Parameters

- **Default Limit**: 15 schema elements per query
- **Similarity Threshold**: 0.2 (configurable)
- **Context Window**: Optimized for GPT-4 token limits

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your-openai-api-key-here
PYTHONPATH=./src

# Database connection (uses settings from common/db_utils.py)
# Default: postgresql://postgres:YourStrong@Passw0rd@localhost:5432/olist
```

### Retrieval Tuning

You can adjust retrieval parameters in `rag_chat_app.py`:

```python
# In generate_sql_query_rag function
relevant_schema = retriever.retrieve_relevant_schema(
    question, 
    limit=15,  # Number of schema elements to retrieve
    similarity_threshold=0.2  # Minimum similarity score
)
```

### Model Configuration

To use a different embedding model:

```python
# In SchemaRAGRetriever class
retriever = SchemaRAGRetriever(model_name="your-preferred-model")
```

Popular alternatives:
- `all-mpnet-base-v2`: Higher quality, larger size
- `all-distilroberta-v1`: Good balance of speed and quality
- `paraphrase-MiniLM-L6-v2`: Optimized for paraphrase detection

## Performance Optimization

### Vector Index Tuning

For large schemas, you may want to tune the HNSW index:

```sql
-- Adjust index parameters for better recall/speed tradeoff
CREATE INDEX idx_schema_embeddings_vector 
ON schema_embeddings USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);
```

### Caching

The system uses Streamlit's `@st.cache_resource` for:
- Sentence transformer model loading
- Database connection pooling

## Comparison with Other Approaches

| Approach | Schema Context | Scalability | Relevance | Performance |
|----------|----------------|-------------|-----------|-------------|
| **RAG (This)** | Dynamic retrieval | ✅ Excellent | ✅ High | ✅ Fast |
| **Plain LLM** | Full schema | ❌ Limited | ⚠️ Medium | ⚠️ Slow |
| **Graph-based** | Graph traversal | ✅ Good | ✅ High | ⚠️ Medium |

### Advantages of RAG Approach

1. **Token Efficiency**: Only uses tokens for relevant schema elements
2. **Scalability**: Handles databases with hundreds of tables
3. **Semantic Understanding**: Finds relevant schema even with indirect relationships
4. **Maintenance**: Automatically adapts as schema evolves (with re-indexing)

### Limitations

1. **Initial Setup**: Requires pgvector extension and embedding generation
2. **Re-indexing**: Schema changes require re-running the indexing process
3. **Embedding Quality**: Depends on the quality of schema descriptions
4. **Cold Start**: First-time model loading takes a few seconds

## Troubleshooting

### Common Issues

**1. pgvector extension not found**
```bash
# Install pgvector (Ubuntu/Debian)
sudo apt install postgresql-15-pgvector

# Install pgvector (macOS with Homebrew)
brew install pgvector
```

**2. No schema embeddings found**
```bash
# Re-run the indexing script
poetry run python src/app/chat/rag/index_schema.py
```

**3. Low quality retrievals**
```bash
# Check if schema has rich descriptions
poetry run enrich-metadata

# Re-index with enriched metadata
poetry run python src/app/chat/rag/index_schema.py
```

**4. Memory issues with sentence transformers**
```python
# Use a smaller model
retriever = SchemaRAGRetriever(model_name="all-MiniLM-L6-v2")
```

### Debug Mode

Enable verbose logging:

```python
import logging
logging.getLogger('rag_database_chat').setLevel(logging.DEBUG)
```

## Future Enhancements

- [ ] **Hybrid Search**: Combine semantic and keyword-based retrieval
- [ ] **Query History**: Learn from previous successful queries  
- [ ] **Schema Evolution**: Automatic detection of schema changes
- [ ] **Multi-database**: Support for multiple database connections
- [ ] **Custom Embeddings**: Fine-tune embeddings for domain-specific terminology
- [ ] **Performance Analytics**: Track retrieval quality and query success rates

## Contributing

When making changes to the RAG system:

1. **Schema Changes**: Update both setup and indexing scripts
2. **Embedding Changes**: Consider backwards compatibility
3. **Retrieval Logic**: Test with various query types
4. **Performance**: Monitor embedding generation and search times

## License

Same as the main project license.