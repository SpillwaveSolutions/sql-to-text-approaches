#!/bin/bash

# Exit on any error
set -e

echo "🚀 Setting up RAG Database Chat System"
echo "This script will:"
echo "  1. Create foreign key relationships"
echo "  2. Set up pgvector extension and schema embeddings table"
echo "  3. Generate and store schema embeddings"
echo ""

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY environment variable is not set."
    echo "   The setup will work, but semantic enrichment will be skipped."
    echo "   Set your API key with: export OPENAI_API_KEY=your-key-here"
    echo ""
fi

echo "Step 1: Creating foreign key relationships..."
poetry run python -c "
from src.app.chat.rag.setup_vector_db import setup_foreign_keys
setup_foreign_keys()
"
if [ $? -eq 0 ]; then
    echo "✅ Foreign key relationships created successfully!"
else
    echo "❌ Error: Foreign key creation failed!"
    exit 1
fi

echo ""
echo "Step 2: Setting up pgvector and schema embeddings..."
poetry run python src/app/chat/rag/setup_vector_db.py
if [ $? -eq 0 ]; then
    echo "✅ pgvector setup completed successfully!"
else
    echo "❌ Error: pgvector setup failed!"
    exit 1
fi

echo ""
echo "Step 3: Generating and storing schema embeddings..."
poetry run python src/app/chat/rag/index_schema.py
if [ $? -eq 0 ]; then
    echo "✅ Schema indexing completed successfully!"
else
    echo "❌ Error: Schema indexing failed!"
    exit 1
fi

echo ""
echo "🎉 RAG Database Chat System setup completed successfully!"
echo ""
echo "You can now run the chat application with:"
echo "  export OPENAI_API_KEY=your-key-here"
echo "  poetry run streamlit run src/app/chat/rag/rag_chat_app.py"
echo ""
echo "The system includes:"
echo "  - Foreign key relationships for data integrity"
echo "  - pgvector extension for semantic search"
echo "  - Schema embeddings for intelligent query assistance"
echo ""