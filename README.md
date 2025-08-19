# Text-to-SQL Approaches Research Project

A comprehensive research project implementing multiple natural language interfaces for analyzing retail transaction data using PostgreSQL and various AI/ML approaches.

## Project Overview

This project explores different approaches to converting natural language questions into SQL queries for business analytics. It includes three distinct implementations, each demonstrating different architectural patterns and trade-offs:

1. **Plain LLM**: Direct prompt chaining using the complete database schema
2. **Graph-Enhanced**: Leverages Neo4j for relationship-aware query generation  
3. **RAG-Based**: Uses pgvector for semantic schema retrieval (recommended for large schemas)

The system provides both textual insights and automatic visualizations through user-friendly Streamlit chat interfaces.

## Architecture & Technologies

- **Database**: PostgreSQL 16 with pgvector extension
- **Graph Database**: Neo4j 5.13 for relationship modeling
- **AI/ML**: OpenAI GPT-4, sentence-transformers, semantic embeddings
- **Web Interface**: Streamlit for interactive chat applications
- **Data Pipeline**: SQLite → PostgreSQL with automated schema enrichment
- **Dependency Management**: Poetry for modern Python package management

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Poetry (install from https://python-poetry.org/)

### 1. Environment Setup

```bash
# Ensure Python 3.12 is active
export PATH="$(brew --prefix)/opt/python@3.12/libexec/bin:$PATH"

# Clone and navigate to project
git clone <repository-url>
cd text-to-sql-approaches

# Install dependencies (choose based on which apps you want to run)
poetry install --with chat,rag,dev  # For all features
```

### 2. Start Infrastructure Services

```bash
# Start PostgreSQL and Neo4j
docker compose up -d

# Verify services are running
docker compose ps
```

### 3. Data Pipeline Setup

```bash
# Set environment variables
export PYTHONPATH=./src
export OPENAI_API_KEY=your-openai-api-key

# Run the complete data pipeline
./src/loadin/run_data_importer.sh

# Generate enhanced metadata (optional but recommended)
poetry run enrich-metadata
```

### 4. Choose Your Text-to-SQL Approach

## Application Options

### Option A: Plain LLM Chat (Simplest)

Best for: Small to medium schemas, quick setup, understanding the baseline approach

```bash
poetry install --with chat
export OPENAI_API_KEY=your-openai-api-key
export PYTHONPATH=./src
poetry run streamlit run src/app/chat/plain_llm/prompt_chain_app.py
```

**Pros**: Simple setup, works immediately  
**Cons**: Limited by LLM context window, includes irrelevant schema information

### Option B: Graph-Enhanced Chat (Relationship-Aware)

Best for: Complex relational queries, understanding data relationships

```bash
poetry install --with chat,graph
export OPENAI_API_KEY=your-openai-api-key
export PYTHONPATH=./src
poetry run streamlit run src/app/chat/graph/graph_chat_app.py
```

**Pros**: Better relationship understanding, graph-based context  
**Cons**: Additional Neo4j dependency, more complex setup

### Option C: RAG-Based Chat (Recommended for Production)

Best for: Large schemas, production use, semantic relevance

```bash
# Install dependencies
poetry install --with chat,rag

# One-time setup: Initialize pgvector and index schema
export PYTHONPATH=./src
poetry run python src/app/chat/rag/setup_vector_db.py
poetry run python src/app/chat/rag/index_schema.py

# Run the application
export OPENAI_API_KEY=your-openai-api-key
export PYTHONPATH=./src
poetry run streamlit run src/app/chat/rag/rag_chat_app.py
```

**Pros**: Scalable, semantic relevance, efficient token usage  
**Cons**: Requires initial indexing, pgvector dependency

## Detailed Setup Instructions

### Poetry Dependency Groups

The project uses Poetry with organized dependency groups:

```bash
# Core dependencies only (for data pipeline)
poetry install

# Add chat interface support
poetry install --with chat

# Add graph database capabilities
poetry install --with chat,graph

# Add RAG/vector search capabilities  
poetry install --with chat,rag

# Development setup (includes testing, formatting, etc.)
poetry install --with chat,rag,graph,dev
```

### Database Configuration

The system connects to PostgreSQL with these defaults:
- **Host**: localhost:5432  
- **Database**: olist
- **Username**: postgres
- **Password**: YourStrong@Passw0rd

Neo4j defaults (for graph approach):
- **URI**: bolt://localhost:7687
- **Username**: neo4j  
- **Password**: password

### Available Poetry Scripts

Poetry provides convenient scripts for common data pipeline tasks:

```bash
# Data pipeline operations
poetry run import-data          # Import SQLite data to PostgreSQL  
poetry run create-fks           # Create foreign key relationships
poetry run get-ddl              # Extract database DDL
poetry run enrich-metadata      # Enhance schema with AI-generated descriptions

# Or run the complete pipeline
./src/loadin/run_data_importer.sh
```

## Understanding the Approaches

### 1. Plain LLM Approach
- Includes entire database schema in every prompt
- Simple and straightforward implementation  
- Limited by LLM context window (~8K-32K tokens)
- Good for understanding baseline performance

### 2. Graph-Enhanced Approach  
- Uses Neo4j to model database relationships
- Provides graph-based context for better relationship understanding
- More sophisticated query planning
- Requires additional graph database infrastructure
- Creates an extension point for adding other datasets and developing cross-dataset semantic relationship linkages (e.g. unstructured input docs like business processes and rules)

### 3. RAG-Based Approach (Recommended)
- Uses semantic embeddings to find relevant schema elements
- Scales to large databases without context window limitations  
- Provides only relevant schema information to the LLM
- Most efficient token usage and query generation

## Example Usage

Once any application is running, you can ask natural language questions:

- "What are the top selling products this month?"
- "Show me customer information for high-value orders"  
- "Which product categories have the best profit margins?"
- "What's the average order value by customer segment?"

Each application will:
1. Generate appropriate SQL queries
2. Execute them against the PostgreSQL database
3. Provide natural language insights  
4. Create automatic visualizations when applicable

## Development Workflow

### Code Formatting and Quality

```bash
# Install development dependencies
poetry install --with dev

# Format code
poetry run black src/
poetry run isort src/

# Lint code  
poetry run flake8 src/

# Run tests
poetry run pytest
```

### Updating Dependencies

```bash
# Add new dependencies
poetry add package-name

# Add to specific group
poetry add --group rag new-rag-package

# Update all dependencies
poetry update
```

## Project Structure

```
├── src/
│   ├── app/chat/              # Three chat applications
│   │   ├── plain_llm/         # Basic prompt chaining
│   │   ├── graph/             # Graph-enhanced queries  
│   │   └── rag/               # RAG-based semantic retrieval
│   ├── common/                # Shared utilities
│   ├── loadin/                # Data ingestion pipeline
│   └── metadata/              # Schema extraction and enrichment
├── data/                      # Sample datasets
├── docs/                      # Additional documentation
├── pyproject.toml             # Poetry configuration
└── docker-compose.yml        # Infrastructure services
```

## Troubleshooting

### Common Issues

**1. Poetry not found**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**2. Docker services not starting**
```bash
docker compose down
docker compose up -d --force-recreate
```

**3. pgvector extension errors (for RAG)**
```bash
# Check if pgvector is installed in your PostgreSQL
docker compose exec postgres psql -U postgres -d olist -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**4. Python import errors**
```bash
# Always set PYTHONPATH when running scripts
export PYTHONPATH=./src
```

### Performance Tips

- **For large schemas**: Use the RAG-based approach
- **For complex relationships**: Try the graph-enhanced approach  
- **For quick prototyping**: Start with the plain LLM approach
- **Memory optimization**: Use smaller embedding models in RAG setup

## Contributing

1. Install development dependencies: `poetry install --with chat,rag,graph,dev`
2. Follow code formatting standards using black and isort
3. Add tests for new functionality
4. Update documentation for any new features

## Research Context

This project serves as a comprehensive comparison of different text-to-SQL architectures:

- **Token efficiency** vs **context completeness**
- **Setup complexity** vs **scalability**  
- **Semantic understanding** vs **deterministic retrieval**
- **Infrastructure requirements** vs **performance benefits**

Each approach demonstrates different trade-offs suitable for various use cases and deployment scenarios.

## License
Copyright Spillwave LLC, 2025
License: OSS / MIT