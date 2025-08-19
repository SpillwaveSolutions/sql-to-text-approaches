import sys
import os
import logging
import json
from datetime import datetime
from typing import List, Dict, Tuple
# Import dependencies

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_database_chat.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('rag_database_chat')

# Import dependencies
from src.common.db_utils import get_db_connection
from src.common.visualization_selector import VisualizationSelector, render_visualization
import streamlit as st
import pandas as pd
from sqlalchemy import text
import openai
from sentence_transformers import SentenceTransformer
from src.common.sql_validator import validate_sql, get_validation_error_context
from src.common.speech_to_text import create_speech_to_text_widget

def check_and_initialize_rag_system():
    """Check if the RAG system is initialized and set it up if needed"""
    try:
        engine = get_db_connection()
        with engine.connect() as conn:
            # Check if schema_embeddings table exists
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_name = 'schema_embeddings' AND table_schema = 'public'
            """)).fetchone()
            
            if not result:
                # Table doesn't exist, need to run full setup
                st.info("🔄 RAG system not initialized. Setting up database and vector embeddings...")
                
                with st.spinner("Setting up RAG system... This may take a few minutes."):
                    # Import setup functions
                    from src.app.chat.rag.setup_vector_db import setup_foreign_keys, setup_pgvector_extension, create_schema_embeddings_table, create_update_trigger
                    from src.app.chat.rag.index_schema import SchemaEmbeddingIndexer
                    
                    # Step 1: Create foreign keys
                    setup_foreign_keys()
                    
                    # Step 2: Setup pgvector
                    setup_pgvector_extension()
                    
                    # Step 3: Create tables
                    create_schema_embeddings_table()
                    create_update_trigger()
                    
                    # Step 4: Index schema
                    indexer = SchemaEmbeddingIndexer()
                    indexer.ensure_foreign_keys()  # Extra safety check
                    indexer.load_model()
                    indexer.clear_existing_embeddings()
                    indexer.generate_and_store_embeddings()
                    
                    st.success("✅ RAG system initialized successfully!")
                    st.rerun()
                    
            else:
                # Table exists, check if it has data
                result = conn.execute(text("SELECT COUNT(*) FROM schema_embeddings")).fetchone()
                embedding_count = result[0] if result else 0
                
                if embedding_count == 0:
                    # Table exists but no embeddings
                    st.info("🔄 RAG database table exists but has no embeddings. Indexing schema...")
                    
                    with st.spinner("Indexing database schema... This may take a few minutes."):
                        # Import indexing functions
                        from src.app.chat.rag.index_schema import SchemaEmbeddingIndexer
                        
                        # Index schema with FK creation
                        indexer = SchemaEmbeddingIndexer()
                        indexer.ensure_foreign_keys()
                        indexer.load_model()
                        indexer.clear_existing_embeddings()
                        indexer.generate_and_store_embeddings()
                        
                        st.success("✅ Schema indexed successfully!")
                        st.rerun()
                
                # If we get here, system is properly initialized
                return embedding_count
                
    except Exception as e:
        st.error(f"⚠️ Failed to initialize RAG system: {str(e)}")
        st.error("Please check the error logs and ensure PostgreSQL and pgvector are properly configured.")
        raise

class SchemaRAGRetriever:
    """RAG retriever for schema information using pgvector"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.engine = get_db_connection()
        
    @st.cache_resource
    def load_model(_self):
        """Load the sentence transformer model (cached for performance)"""
        _self.model = SentenceTransformer(_self.model_name)
        return _self.model
    
    def retrieve_relevant_schema(self, query: str, limit: int = 10, similarity_threshold: float = 0.3) -> List[Dict]:
        """
        Retrieve relevant schema elements using semantic search
        
        Args:
            query: User's natural language query
            limit: Maximum number of schema elements to retrieve
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            List of relevant schema elements with metadata
        """
        if self.model is None:
            self.model = self.load_model()
        
        logger.info(f"Retrieving schema for query: {query}")
        
        # Generate embedding for the query
        query_embedding = self.model.encode([query])[0].tolist()
        
        # Search for similar schema elements
        search_sql = """
        SELECT 
            schema_name, table_name, column_name, element_type,
            description, full_context, metadata,
            1 - (embedding <=> (:query_vector)::vector) as similarity
        FROM schema_embeddings
        WHERE 1 - (embedding <=> (:query_vector)::vector) >= :threshold
        ORDER BY embedding <=> (:query_vector)::vector
        LIMIT :limit
        """
        
        try:
            with self.engine.connect() as conn:
                # Convert list to string for PostgreSQL vector type
                vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
                results = conn.execute(text(search_sql), {
                    'query_vector': vector_str,
                    'limit': limit,
                    'threshold': similarity_threshold
                }).fetchall()
            
            schema_elements = []
            for row in results:
                schema_elements.append({
                    'schema_name': row.schema_name,
                    'table_name': row.table_name,
                    'column_name': row.column_name,
                    'element_type': row.element_type,
                    'description': row.description,
                    'full_context': row.full_context,
                    'metadata': row.metadata if isinstance(row.metadata, dict) else (json.loads(row.metadata) if row.metadata else {}),
                    'similarity': float(row.similarity)
                })
            
            logger.info(f"Retrieved {len(schema_elements)} relevant schema elements")
            return schema_elements
            
        except Exception as e:
            logger.error(f"Error retrieving schema: {str(e)}")
            st.error(f"Error retrieving schema information: {str(e)}")
            return []
    
    def format_retrieved_schema(self, schema_elements: List[Dict]) -> str:
        """
        Format retrieved schema elements into a context string for the LLM
        
        Args:
            schema_elements: List of retrieved schema elements
            
        Returns:
            Formatted schema context string
        """
        if not schema_elements:
            return "No relevant schema information found."
        
        # Group by tables
        tables_info = {}
        for element in schema_elements:
            table_name = element['table_name']
            if table_name not in tables_info:
                tables_info[table_name] = {
                    'table_info': None,
                    'columns': [],
                    'similarity_scores': []
                }
            
            if element['element_type'] == 'table':
                tables_info[table_name]['table_info'] = element
            else:
                tables_info[table_name]['columns'].append(element)
            
            tables_info[table_name]['similarity_scores'].append(element['similarity'])
        
        # Format context
        context_parts = []
        context_parts.append("RELEVANT DATABASE SCHEMA INFORMATION:")
        context_parts.append("=" * 50)
        
        for table_name, info in tables_info.items():
            avg_similarity = sum(info['similarity_scores']) / len(info['similarity_scores'])
            context_parts.append(f"\nTable: {table_name} (Relevance: {avg_similarity:.3f})")
            
            if info['table_info'] and info['table_info']['description']:
                context_parts.append(f"Description: {info['table_info']['description']}")
            
            if info['columns']:
                context_parts.append("Relevant Columns:")
                for col in sorted(info['columns'], key=lambda x: x['similarity'], reverse=True):
                    col_desc = f"  - {col['column_name']} ({col['metadata'].get('data_type', 'unknown')})"
                    if not col['metadata'].get('is_nullable', True):
                        col_desc += " NOT NULL"
                    if col['metadata'].get('is_primary_key'):
                        col_desc += " PRIMARY KEY"
                    if col['metadata'].get('is_foreign_key'):
                        col_desc += " FOREIGN KEY"
                    if col['description']:
                        col_desc += f" - {col['description']}"
                    col_desc += f" [Similarity: {col['similarity']:.3f}]"
                    context_parts.append(col_desc)
        
        return "\n".join(context_parts)

def get_db_summary_rag() -> str:
    """Generate database summary using RAG approach with LLM analysis"""
    logger.info("Generating database summary using RAG with LLM")
    
    retriever = SchemaRAGRetriever()
    
    # Use a broad query to get comprehensive database information
    general_schema = retriever.retrieve_relevant_schema(
        "database tables entities business data structure relationships", 
        limit=30,
        similarity_threshold=0.05  # Lower threshold to get more comprehensive coverage
    )
    
    if not general_schema:
        return "Unable to retrieve database schema information. Please ensure the schema has been indexed."
    
    # Format the retrieved schema for LLM analysis
    schema_context = retriever.format_retrieved_schema(general_schema)
    
    system_prompt = """You are a helpful database expert. Given the database schema information retrieved through semantic search, provide a concise summary of:
    1. The database's main purpose and domain
    2. Key entities/tables and their relationships
    3. Types/examples of practical questions users can ask
    
    Keep the response under 200 words and focus on practical usage. Make it conversational and informative for business users."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is the database schema information:\n\n{schema_context}"}
    ]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        summary = response.choices[0].message.content
        logger.info("Database summary generated successfully using LLM")
        return summary
    except Exception as e:
        logger.error(f"Error generating database summary with LLM: {str(e)}")
        # Fallback to basic summary
        tables = list(set([elem['table_name'] for elem in general_schema]))
        table_count = len(tables)
        fallback_summary = [
            f"This database contains {table_count} main tables: {', '.join(tables)}.",
            "The database appears to be designed for retail/e-commerce analytics based on the available schema.",
            "You can ask questions about customer information, orders, products, and sales data."
        ]
        return "\n".join(fallback_summary)

def generate_sql_query_rag_with_correction(question: str, max_retries: int = 3) -> Dict:
    """Generate SQL query using RAG with self-correction capabilities"""
    logger.info(f"Generating SQL query with correction for: {question}")
    
    last_error = None
    retrieval_strategies = [
        # Strategy 1: Standard retrieval
        {"limit": 15, "similarity_threshold": 0.2, "description": "standard"},
        # Strategy 2: Expanded retrieval with more context
        {"limit": 25, "similarity_threshold": 0.15, "description": "expanded context"},
        # Strategy 3: Broad retrieval with lower threshold
        {"limit": 35, "similarity_threshold": 0.1, "description": "broad context"}
    ]
    
    for attempt in range(max_retries):
        strategy = retrieval_strategies[min(attempt, len(retrieval_strategies) - 1)]
        error_context = f"Previous attempt {attempt} failed: {str(last_error)}" if last_error else None
        
        logger.info(f"Attempt {attempt + 1}/{max_retries} using {strategy['description']} strategy")
        
        try:
            # Generate query with current strategy
            query_result = generate_sql_query_rag(
                question=question,
                error_context=error_context,
                limit=strategy["limit"],
                similarity_threshold=strategy["similarity_threshold"]
            )
            
            # Validate the query using the SQL validator
            validation_result = validate_sql(query_result['sql'], skip_syntax=False)
            if not validation_result['is_valid']:
                raise ValueError(validation_result['error'])
                
            logger.info(f"Query validation successful on attempt {attempt + 1}")
            return query_result
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
            
            # Generate detailed error context for next attempt
            if attempt < max_retries - 1:
                # Try to get more detailed error context from the validator if available
                try:
                    validation_result = validate_sql(query_result['sql'], skip_syntax=True)
                    if not validation_result['is_valid']:
                        error_context = get_validation_error_context(validation_result)
                        logger.info(f"Detailed validation error context: {error_context}")
                except:
                    pass  # Use the original error if validation context fails
                
                if "does not exist" in error_msg or "column" in error_msg.lower():
                    logger.info("Column/table error detected, will expand schema context in next attempt")
                elif "relation" in error_msg.lower():
                    logger.info("Relationship error detected, will include more table relationships")
                
                continue
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {error_msg}")
                # Return the best attempt with error information
                return {
                    "sql": "-- Query generation failed after multiple attempts",
                    "explanation": f"Failed to generate valid query after {max_retries} attempts. Last error: {error_msg}",
                    "tables_used": [],
                    "expected_result_type": "error",
                    "schema_elements_used": [],
                    "error": error_msg,
                    "attempts": attempt + 1
                }
    
    # Should not reach here
    return {"error": "Unexpected error in query generation"}

def generate_sql_query_rag(question: str, error_context: str = None, limit: int = 15, similarity_threshold: float = 0.2) -> Dict:
    """Generate SQL query using RAG-retrieved schema context"""
    context_msg = f" with error context: {error_context}" if error_context else ""
    logger.info(f"Generating SQL query using RAG for question: {question}{context_msg}")
    
    # Initialize RAG retriever
    retriever = SchemaRAGRetriever()
    
    # Retrieve relevant schema elements
    relevant_schema = retriever.retrieve_relevant_schema(
        question, 
        limit=limit, 
        similarity_threshold=similarity_threshold
    )
    
    if not relevant_schema:
        raise ValueError("No relevant schema information found for this question. Please ensure the database schema has been properly indexed.")
    
    # Format schema context
    schema_context = retriever.format_retrieved_schema(relevant_schema)
    
    system_prompt = """You are an expert PostgreSQL query generator with error correction capabilities. Given a user's question and 
    relevant database schema information retrieved via semantic search, generate a SQL query that answers the question.

    IMPORTANT: The schema information provided has been retrieved based on semantic similarity to the user's question,
    so it should contain the most relevant tables and columns needed to answer the question.

    Return your response in the following JSON structure:
    {
        "sql": "the SQL query",
        "explanation": "brief explanation of how the query answers the question",
        "tables_used": ["list", "of", "tables", "used"],
        "expected_result_type": "single_value|list|count|aggregate",
        "schema_elements_used": ["list", "of", "schema", "elements", "that", "were", "key", "to", "answering"]
    }

    Guidelines for query generation:
    1. Use ONLY the tables and columns provided in the schema context
    2. Generate a precise PostgreSQL query that answers the question
    3. Analyze table relationships carefully - look for connecting tables (like order_items connecting products to orders)
    4. When joining tables, ensure you understand the relationship path (e.g., products -> order_items -> orders -> order_reviews)
    5. Use appropriate JOINs and WHERE clauses based on the schema relationships
    6. Keep the query efficient and focused
    7. When asked to return a list of things, reasonably limit the number of results to 10 unless the user has indicated otherwise
    8. When asked to return a count, return the count
    9. When asked to return a single value, return the value
    10. When a table references another table that will add meaningful additional information, perform the join and include the detail
    11. Ensure the SQL syntax is consistent with PostgreSQL dialect
    12. Use proper table and column names as provided in the schema context
    13. If previous attempts failed, carefully review the error and adjust the query accordingly"""

    if error_context:
        system_prompt += f"\n\nPrevious attempt failed with error: {error_context}\nPlease fix the query accordingly."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{schema_context}\n\nQuestion: {question}"}
    ]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.1,
            max_tokens=700,
            response_format={ "type": "json_object" }
        )
        
        query_info = json.loads(response.choices[0].message.content)
        logger.info(f"Generated SQL query: {query_info.get('sql', 'N/A')}")
        return query_info
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        raise ValueError(f"Failed to generate valid SQL query. JSON parse error: {e}")
    except Exception as e:
        logger.error(f"Error generating SQL query: {str(e)}")
        raise

def execute_query(sql_query: str) -> Tuple[pd.DataFrame, str]:
    """Execute SQL query and return results with status message"""
    logger.info("Executing SQL query")
    
    try:
        engine = get_db_connection()
        
        with engine.connect() as conn:
            result = pd.read_sql_query(sql_query, conn)
        
        if result.empty:
            status = "Query executed successfully but returned no results."
            logger.info("Query returned no results")
        else:
            status = f"Query executed successfully. Retrieved {len(result)} rows."
            logger.info(f"Query successful, {len(result)} rows returned")
        
        return result, status
        
    except Exception as e:
        error_msg = f"Query execution failed: {str(e)}"
        logger.error(error_msg)
        return pd.DataFrame(), error_msg

def analyze_query_result(question: str, query_info: Dict, result: pd.DataFrame) -> str:
    """Generate analysis and insights from query results"""
    logger.info("Analyzing query results")
    
    if result.empty:
        return "The query returned no results. You may want to modify your question or check if the data exists in the database."
    
    # Prepare result summary
    result_summary = f"Query returned {len(result)} rows with {len(result.columns)} columns.\n"
    result_summary += f"Columns: {', '.join(result.columns.tolist())}\n\n"
    
    # Show first few rows as context
    if len(result) <= 10:
        result_summary += "All results:\n" + result.to_string(index=False)
    else:
        result_summary += "First 5 rows:\n" + result.head().to_string(index=False)
        result_summary += f"\n\n... and {len(result) - 5} more rows"
    
    system_prompt = """You are a data analyst. Given a user's question, the SQL query that was generated, 
    and the results, provide insights and a natural language summary of the findings.

    Be specific about the numbers and data found. If there are interesting patterns or notable findings, 
    highlight them. Keep the response conversational and informative."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""
Question: {question}

SQL Query: {query_info.get('sql', 'N/A')}
Query Explanation: {query_info.get('explanation', 'N/A')}

Results Summary:
{result_summary}

Please provide insights and analysis of these results."""}
    ]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=400
        )
        
        analysis = response.choices[0].message.content
        logger.info("Analysis generated successfully")
        return analysis
        
    except Exception as e:
        logger.error(f"Error generating analysis: {str(e)}")
        return f"Analysis generation failed: {str(e)}"

def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="RAG Database Chat", 
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 RAG Database Chat")
    st.subheader("Ask questions about your data using semantic schema retrieval")
    
    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'db_summary' not in st.session_state:
        with st.spinner("Loading database schema information..."):
            try:
                # First, ensure RAG system is initialized
                check_and_initialize_rag_system()
                
                # Then get the database summary
                st.session_state.db_summary = get_db_summary_rag()
            except Exception as e:
                st.error(f"Failed to load database information: {str(e)}")
                st.error("Please ensure PostgreSQL and pgvector are properly configured.")
                return
    
    # Sidebar with database info
    with st.sidebar:
        st.header("Database Information")
        st.write(st.session_state.db_summary)
        
        st.header("🔧 RAG System Controls")
        
        # Rebuild button
        if st.button("🔄 Rebuild Schema Index", help="Rebuild the vector embeddings from the latest PostgreSQL schema"):
            try:
                with st.spinner("Rebuilding schema index..."):
                    # Import indexing functions
                    from src.app.chat.rag.index_schema import SchemaEmbeddingIndexer
                    
                    # Rebuild schema index with FK creation
                    indexer = SchemaEmbeddingIndexer()
                    indexer.ensure_foreign_keys()
                    indexer.load_model()
                    indexer.clear_existing_embeddings()
                    indexer.generate_and_store_embeddings()
                
                # Clear the cached summary to force regeneration
                if 'db_summary' in st.session_state:
                    del st.session_state.db_summary
                
                st.success("✅ Schema index rebuilt successfully!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Error rebuilding schema index: {str(e)}")
        
        # System status
        try:
            engine = get_db_connection()
            with engine.connect() as conn:
                # Check embeddings count
                result = conn.execute(text("SELECT COUNT(*) FROM schema_embeddings")).fetchone()
                embedding_count = result[0] if result else 0
                
                # Check table and column counts  
                result = conn.execute(text("SELECT COUNT(DISTINCT table_name) FROM schema_embeddings WHERE element_type = 'table'")).fetchone()
                table_count = result[0] if result else 0
                
                result = conn.execute(text("SELECT COUNT(*) FROM schema_embeddings WHERE element_type = 'column'")).fetchone()
                column_count = result[0] if result else 0
                
                st.metric("Vector Embeddings", f"{embedding_count:,}")
                st.metric("Indexed Tables", f"{table_count:,}")  
                st.metric("Indexed Columns", f"{column_count:,}")
                
                if embedding_count > 0:
                    st.success("✅ RAG system ready")
                else:
                    st.error("❌ No embeddings found")
                    
        except Exception as e:
            st.error(f"❌ Status check failed: {str(e)}")
        
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "data" in message:
                st.write(message["content"])
                
                # Display data table
                if not message["data"].empty:
                    st.subheader("Query Results")
                    st.dataframe(message["data"], use_container_width=True)
                    
                    # Generate and display visualization if applicable
                    if len(message["data"]) > 0:
                        try:
                            viz_selector = VisualizationSelector()
                            # Get the original question from the query_info if available
                            query_text = message.get("query_info", {}).get("sql", "")
                            chart_config = viz_selector.select_visualization(message["data"], query_text)
                            if chart_config and chart_config.get('type') != 'none':
                                st.subheader("Visualization")
                                render_visualization(chart_config, message["data"], st)
                        except Exception as e:
                            logger.error(f"Visualization error: {str(e)}")
                
                # Display schema elements used (if available)
                if "query_info" in message and "schema_elements_used" in message["query_info"]:
                    with st.expander("Schema Elements Used"):
                        for element in message["query_info"]["schema_elements_used"]:
                            st.code(element)
            else:
                st.write(message["content"])
    
    # Voice and text input section
    st.divider()
    col1, col2 = st.columns([5, 1])
    
    with col1:
        # Initialize session state for voice transcript
        if 'voice_transcript' not in st.session_state:
            st.session_state.voice_transcript = ""
        
        # Text input with voice transcript if available
        input_value = st.session_state.voice_transcript
        prompt = st.text_input(
            "Ask a question about your data...",
            value=input_value,
            key="user_input",
            placeholder="Type your question or use the microphone"
        )
    
    with col2:
        st.write(" ")  # Add some spacing to align with text input
        
        # Add a help tooltip for voice input
        st.markdown("🎤 **Voice Input**")
        with st.expander("ℹ️ Voice Help", expanded=False):
            st.write("""
            **How to use voice input:**
            1. Click the 🎤 microphone button
            2. Allow microphone access if prompted
            3. Speak your question clearly (3+ seconds)
            4. Click ⏹️ to stop recording
            5. Your text will appear in the input box
            
            **Example questions:**
            - "Show me the top 10 customers by sales"
            - "What are the most popular products?"
            - "How many orders were placed last month?"
            """)
        
        # Speech-to-text recorder
        try:
            transcript = create_speech_to_text_widget(
                key="rag_voice_input",
                start_prompt="🎤",
                stop_prompt="⏹️",
                language="auto"
            )
            
            # Update session state if we get a new transcript
            if transcript and transcript != st.session_state.voice_transcript:
                st.session_state.voice_transcript = transcript
                st.rerun()  # Refresh to update the text input
                
        except Exception as e:
            logger.error(f"Voice input error: {e}")
            st.error("🎤 Voice input unavailable")
    
    # Submit button
    submit_clicked = st.button("Send", key="send_button", type="primary")
    
    # Process input if we have a prompt (from typing or voice) and submit was clicked
    if submit_clicked and prompt and prompt.strip():
        # Clear the voice transcript after using it
        st.session_state.voice_transcript = ""
        
        # Display user message
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            try:
                with st.spinner("Retrieving relevant schema and generating SQL..."):
                    query_info = generate_sql_query_rag_with_correction(prompt)
                
                with st.spinner("Executing query..."):
                    result_df, status = execute_query(query_info["sql"])
                
                if not result_df.empty:
                    with st.spinner("Analyzing results..."):
                        analysis = analyze_query_result(prompt, query_info, result_df)
                    
                    # Format response
                    response_parts = []
                    response_parts.append(f"**Query Explanation:** {query_info.get('explanation', 'N/A')}")
                    response_parts.append(f"**Status:** {status}")
                    response_parts.append(f"**Analysis:** {analysis}")
                    
                    response = "\n\n".join(response_parts)
                    
                    st.write(response)
                    
                    # Display results
                    st.subheader("Query Results")
                    st.dataframe(result_df, use_container_width=True)
                    
                    # Show SQL query
                    with st.expander("View SQL Query"):
                        st.code(query_info["sql"], language="sql")
                    
                    # Show schema elements used
                    if "schema_elements_used" in query_info:
                        with st.expander("Schema Elements Used"):
                            for element in query_info["schema_elements_used"]:
                                st.code(element)
                    
                    # Generate visualization
                    if len(result_df) > 0:
                        try:
                            viz_selector = VisualizationSelector()
                            chart_config = viz_selector.select_visualization(result_df, query_info["sql"])
                            if chart_config and chart_config.get('type') != 'none':
                                st.subheader("Visualization")
                                render_visualization(chart_config, result_df, st)
                        except Exception as e:
                            logger.error(f"Visualization error: {str(e)}")
                    
                    # Save to session state
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response,
                        "data": result_df,
                        "query_info": query_info
                    })
                else:
                    error_response = f"**Status:** {status}"
                    st.write(error_response)
                    
                    # Show SQL query for debugging
                    with st.expander("View SQL Query"):
                        st.code(query_info["sql"], language="sql")
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": error_response,
                        "data": result_df,
                        "query_info": query_info
                    })
                
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

if __name__ == "__main__":
    main()